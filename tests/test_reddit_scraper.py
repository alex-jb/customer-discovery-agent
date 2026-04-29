"""Tests for reddit_scraper.py — keyword matching + graceful degrade.

praw is mocked at the import level so tests run with no Reddit creds and
no network.
"""
from __future__ import annotations
import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from customer_discovery_agent.reddit_scraper import (
    _has_pain_match,
    is_configured,
    scrape_subreddit,
    scrape_many,
    DEFAULT_PAIN_KEYWORDS,
)


# ─── _has_pain_match ──────────────────────────────────────────

def test_pain_match_returns_subset():
    text = "I wish there was a tool to fix this — anyone use Notion?"
    matched = _has_pain_match(text, ["i wish", "anyone use", "frustrated"])
    assert sorted(matched) == ["anyone use", "i wish"]


def test_pain_match_case_insensitive():
    matched = _has_pain_match("I'M FRUSTRATED WITH SUPABASE", ["frustrated"])
    assert matched == ["frustrated"]


def test_pain_match_empty_when_no_match():
    assert _has_pain_match("just shipping cool stuff", DEFAULT_PAIN_KEYWORDS) == []


# ─── is_configured ────────────────────────────────────────────

def test_is_configured_false_when_missing(monkeypatch):
    for k in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
              "REDDIT_USERNAME", "REDDIT_PASSWORD", "REDDIT_USER_AGENT"):
        monkeypatch.delenv(k, raising=False)
    assert is_configured() is False


def test_is_configured_true_when_all_set(monkeypatch):
    for k in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
              "REDDIT_USERNAME", "REDDIT_PASSWORD", "REDDIT_USER_AGENT"):
        monkeypatch.setenv(k, "x")
    assert is_configured() is True


def test_is_configured_false_when_one_missing(monkeypatch):
    for k in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
              "REDDIT_USERNAME", "REDDIT_PASSWORD"):
        monkeypatch.setenv(k, "x")
    monkeypatch.delenv("REDDIT_USER_AGENT", raising=False)
    assert is_configured() is False


# ─── scrape_subreddit ──────────────────────────────────────────

def test_scrape_returns_empty_when_unconfigured(monkeypatch):
    for k in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
              "REDDIT_USERNAME", "REDDIT_PASSWORD", "REDDIT_USER_AGENT"):
        monkeypatch.delenv(k, raising=False)
    assert scrape_subreddit("SaaS") == []


def _fake_post(*, id_, title, selftext, score, created_offset_h=1,
                num_comments=3, author="testuser"):
    """Build a praw-shaped fake submission."""
    p = MagicMock()
    p.id = id_
    p.title = title
    p.selftext = selftext
    p.score = score
    p.num_comments = num_comments
    p.permalink = f"/r/SaaS/comments/{id_}/x"
    p.created_utc = (datetime.now(timezone.utc).timestamp()
                     - created_offset_h * 3600)
    p.author = author
    return p


def _wire_praw(monkeypatch, posts_new, posts_top):
    """Set up env + mock praw module so scrape_subreddit returns our posts."""
    for k in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
              "REDDIT_USERNAME", "REDDIT_PASSWORD", "REDDIT_USER_AGENT"):
        monkeypatch.setenv(k, "x")
    fake_sub = MagicMock()
    fake_sub.new.return_value = iter(posts_new)
    fake_sub.top.return_value = iter(posts_top)
    fake_reddit = MagicMock()
    fake_reddit.subreddit.return_value = fake_sub
    fake_praw = MagicMock()
    fake_praw.Reddit.return_value = fake_reddit
    monkeypatch.setitem(sys.modules, "praw", fake_praw)


def test_scrape_filters_by_keywords(monkeypatch):
    posts = [
        _fake_post(id_="a", title="I wish I had a launcher",
                    selftext="for my SaaS", score=10),
        _fake_post(id_="b", title="Just shipped", selftext="cool", score=20),
    ]
    _wire_praw(monkeypatch, posts, [])
    out = scrape_subreddit("SaaS", keywords=["i wish"], min_score=5)
    assert len(out) == 1
    assert out[0].source_id == "reddit/a"
    assert "i wish" in out[0].keywords_matched


def test_scrape_filters_by_min_score(monkeypatch):
    posts = [
        _fake_post(id_="lowscore", title="i wish for X", selftext="", score=2),
        _fake_post(id_="highscore", title="i wish for Y", selftext="", score=50),
    ]
    _wire_praw(monkeypatch, posts, [])
    out = scrape_subreddit("SaaS", keywords=["i wish"], min_score=10)
    assert len(out) == 1
    assert out[0].source_id == "reddit/highscore"


def test_scrape_filters_by_age(monkeypatch):
    posts = [
        _fake_post(id_="recent", title="i wish A", selftext="", score=10,
                    created_offset_h=2),
        _fake_post(id_="old", title="i wish B", selftext="", score=10,
                    created_offset_h=200),  # 200h > 168h default cutoff
    ]
    _wire_praw(monkeypatch, posts, [])
    out = scrape_subreddit("SaaS", hours=168, keywords=["i wish"], min_score=5)
    ids = [p.source_id for p in out]
    assert "reddit/recent" in ids
    assert "reddit/old" not in ids


def test_scrape_dedupes_across_streams(monkeypatch):
    """Same post showing in both new() and top() should appear once."""
    same = _fake_post(id_="dup", title="i wish C", selftext="", score=10)
    _wire_praw(monkeypatch, [same], [same])
    out = scrape_subreddit("SaaS", keywords=["i wish"], min_score=5)
    assert len(out) == 1


def test_scrape_handles_deleted_author(monkeypatch):
    p = _fake_post(id_="d", title="i wish D", selftext="", score=10)
    p.author = None  # praw sets to None for deleted authors
    _wire_praw(monkeypatch, [p], [])
    out = scrape_subreddit("SaaS", keywords=["i wish"], min_score=5)
    assert len(out) == 1
    assert out[0].author == "[deleted]"


def test_scrape_handles_none_selftext(monkeypatch):
    p = _fake_post(id_="e", title="i wish E", selftext=None, score=10)
    _wire_praw(monkeypatch, [p], [])
    out = scrape_subreddit("SaaS", keywords=["i wish"], min_score=5)
    assert len(out) == 1
    assert out[0].body == ""


# ─── scrape_many ──────────────────────────────────────────────

def test_scrape_many_dedupes_across_subreddits(monkeypatch):
    same_post = _fake_post(id_="cross", title="i wish F", selftext="", score=10)
    _wire_praw(monkeypatch, [same_post], [])
    # praw.subreddit() returns the same fake for any sub name → both calls
    # see the same post; dedup by source_id
    out = scrape_many(["SaaS", "IndieHackers"], keywords=["i wish"], min_score=5)
    assert len(out) == 1


def test_scrape_many_empty_when_unconfigured(monkeypatch):
    for k in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
              "REDDIT_USERNAME", "REDDIT_PASSWORD", "REDDIT_USER_AGENT"):
        monkeypatch.delenv(k, raising=False)
    assert scrape_many(["SaaS"]) == []
