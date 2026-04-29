"""Smoke + unit tests for customer-discovery-agent v0.1."""
from __future__ import annotations
from datetime import datetime, timezone

import pytest

from customer_discovery_agent.cluster import (
    cluster, heuristic_cluster, llm_cluster,
)
from customer_discovery_agent.digest import render_markdown
from customer_discovery_agent.reddit_scraper import (
    DEFAULT_PAIN_KEYWORDS, _has_pain_match, is_configured, scrape_many,
)
from customer_discovery_agent.types import Cluster, Digest, PainPoint


def _pp(title: str, score: int = 10,
         keywords: list[str] | None = None) -> PainPoint:
    return PainPoint(
        source="reddit",
        source_id=f"reddit/{abs(hash(title)) % 10000000}",
        url=f"https://reddit.com/r/SaaS/comments/{title.replace(' ', '-')}",
        title=title, body=title, author="alice",
        score=score, n_comments=3,
        created_at=datetime.now(timezone.utc),
        keywords_matched=keywords or [],
    )


# ───── reddit_scraper unit tests ─────


def test_has_pain_match_finds_keyword():
    text = "Honestly I'm frustrated trying to integrate Stripe with Supabase"
    out = _has_pain_match(text, ["frustrated", "stuck on"])
    assert "frustrated" in out
    assert "stuck on" not in out


def test_has_pain_match_case_insensitive():
    out = _has_pain_match("I WISH there was a tool", ["i wish"])
    assert "i wish" in out


def test_default_pain_keywords_nonempty():
    assert len(DEFAULT_PAIN_KEYWORDS) >= 10


def test_scrape_many_returns_empty_without_creds(monkeypatch):
    for k in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
                "REDDIT_USERNAME", "REDDIT_PASSWORD", "REDDIT_USER_AGENT"):
        monkeypatch.delenv(k, raising=False)
    assert is_configured() is False
    assert scrape_many(["SaaS"]) == []


# ───── cluster unit tests ─────


def test_heuristic_cluster_groups_by_first_keyword():
    pain = [
        _pp("I wish there was a Stripe alternative", keywords=["i wish"]),
        _pp("I wish someone made a CRM for makers", keywords=["i wish"]),
        _pp("Frustrated with Vercel build minutes",  keywords=["frustrated"]),
    ]
    cs = heuristic_cluster(pain)
    summaries = [c.summary for c in cs]
    assert any('"i wish"' in s for s in summaries)
    assert any('"frustrated"' in s for s in summaries)


def test_heuristic_cluster_returns_empty_when_no_input():
    assert heuristic_cluster([]) == []


def test_heuristic_cluster_caps_at_max():
    # 10 unique keywords → 10 single-post clusters; cap at 7
    pain = [_pp(f"post {i}", keywords=[f"kw{i}"]) for i in range(10)]
    cs = heuristic_cluster(pain, max_clusters=7)
    assert len(cs) == 7


def test_llm_cluster_returns_none_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    pain = [_pp("test", keywords=["i wish"])]
    assert llm_cluster(pain) is None


def test_cluster_falls_back_to_heuristic_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    pain = [_pp("test", keywords=["i wish"])]
    out = cluster(pain)
    assert isinstance(out, list)
    assert len(out) == 1


# ───── digest unit tests ─────


def test_render_markdown_includes_metadata():
    d = Digest(
        window_hours=168, sources=["reddit"], keywords=["i wish"],
        n_pain_points=3,
        clusters=[Cluster(
            cluster_id="c0", summary="Posts about onboarding pain",
            representative_quote="I wish onboarding was easier",
            n_posts=3, avg_score=42.5,
            sample_urls=["https://reddit.com/r/x/comments/a"],
        )],
    )
    md = render_markdown(d)
    assert "Customer Discovery Digest" in md
    assert "168h" in md
    assert "reddit" in md
    assert "Posts about onboarding pain" in md
    assert "https://reddit.com/r/x/comments/a" in md


def test_render_markdown_empty_clusters_message():
    d = Digest(window_hours=24, sources=["reddit"], keywords=[],
                 n_pain_points=0, clusters=[])
    md = render_markdown(d)
    assert "no pain points matched" in md


# ───── pydantic model tests ─────


def test_painpoint_validates_required_fields():
    with pytest.raises(Exception):
        PainPoint(source="reddit")  # missing required fields


def test_cluster_caps_sample_urls_at_5():
    c = Cluster(cluster_id="c", summary="x",
                  representative_quote="y", n_posts=10, avg_score=1.0,
                  sample_urls=["u" + str(i) for i in range(5)])
    assert len(c.sample_urls) == 5
