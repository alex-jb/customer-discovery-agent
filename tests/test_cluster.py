"""Tests for cluster.py — heuristic + LLM modes + fallback chain."""
from __future__ import annotations
import json
import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from customer_discovery_agent.cluster import (
    heuristic_cluster, llm_cluster, cluster as combined_cluster,
)
from customer_discovery_agent.types import PainPoint
from solo_founder_os.anthropic_client import AnthropicClient
from solo_founder_os.testing import fake_anthropic, fake_anthropic_raises


def _pp(id_="a", title="t", body="b", score=10, kws=None):
    return PainPoint(
        source="reddit",
        source_id=f"reddit/{id_}",
        url=f"https://reddit.com/r/SaaS/comments/{id_}/x",
        title=title,
        body=body,
        author="me",
        score=score,
        n_comments=1,
        created_at=datetime.now(timezone.utc),
        keywords_matched=kws or [],
    )


def _client_with_fake(monkeypatch, fake_sdk_client) -> AnthropicClient:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    c = AnthropicClient(usage_log_path=None)
    c._client = fake_sdk_client
    return c


# ─── heuristic_cluster ────────────────────────────────────────

def test_heuristic_empty_returns_empty():
    assert heuristic_cluster([]) == []


def test_heuristic_groups_by_first_keyword():
    pps = [
        _pp(id_="a", title="x", score=5, kws=["i wish"]),
        _pp(id_="b", title="y", score=20, kws=["i wish"]),
        _pp(id_="c", title="z", score=10, kws=["frustrated"]),
    ]
    out = heuristic_cluster(pps)
    by_summary = {c.summary: c for c in out}
    # "i wish" group has 2 members, picks higher-score post as rep
    assert any(c.n_posts == 2 and "i wish" in c.summary for c in out)
    assert any(c.n_posts == 1 and "frustrated" in c.summary for c in out)


def test_heuristic_uncategorized_bucket_for_unmatched():
    pps = [_pp(id_="x", kws=[])]
    out = heuristic_cluster(pps)
    assert any("uncategorized" in c.summary.lower() for c in out)


def test_heuristic_caps_at_max_clusters():
    # 10 distinct keywords; max_clusters=3 should yield 3
    pps = [_pp(id_=f"p{i}", kws=[f"kw{i}"]) for i in range(10)]
    out = heuristic_cluster(pps, max_clusters=3)
    assert len(out) == 3


def test_heuristic_picks_top_scored_as_representative():
    pps = [
        _pp(id_="low", title="LOW", score=1, kws=["i wish"]),
        _pp(id_="high", title="HIGH", score=999, kws=["i wish"]),
    ]
    out = heuristic_cluster(pps)
    assert "HIGH" in out[0].representative_quote


# ─── llm_cluster ──────────────────────────────────────────────

def test_llm_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert llm_cluster([_pp()]) is None


def test_llm_returns_empty_for_empty_input(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert llm_cluster([]) == []


def test_llm_parses_structured_json(monkeypatch):
    pps = [_pp(id_="a"), _pp(id_="b"), _pp(id_="c")]
    fake = fake_anthropic(json.dumps({
        "clusters": [{
            "summary": "Launch tooling pain",
            "representative_quote": "I wish PH had a better preview",
            "member_indices": [0, 1, 2],
        }]
    }))
    client = _client_with_fake(monkeypatch, fake)
    out = llm_cluster(pps, client=client)
    assert len(out) == 1
    assert out[0].summary == "Launch tooling pain"
    assert out[0].n_posts == 3


def test_llm_returns_none_on_unparseable(monkeypatch):
    """v0.3 uses structured outputs; if API returns non-JSON despite the
    beta flag, llm_cluster returns None (caller falls back to heuristic)."""
    fake = fake_anthropic("not json at all")
    client = _client_with_fake(monkeypatch, fake)
    assert llm_cluster([_pp()], client=client) is None


def test_llm_returns_none_on_exception(monkeypatch):
    fake = fake_anthropic_raises(Exception("rate limit"))
    client = _client_with_fake(monkeypatch, fake)
    assert llm_cluster([_pp()], client=client) is None


def test_llm_skips_clusters_with_no_valid_indices(monkeypatch):
    # member_indices all out of range → cluster gets skipped
    fake = fake_anthropic(json.dumps({
        "clusters": [
            {"summary": "valid", "representative_quote": "x", "member_indices": [0]},
            {"summary": "out_of_range", "representative_quote": "y",
             "member_indices": [99, 100]},
        ]
    }))
    client = _client_with_fake(monkeypatch, fake)
    out = llm_cluster([_pp(id_="a")], client=client)
    assert len(out) == 1
    assert out[0].summary == "valid"


# ─── combined cluster() ───────────────────────────────────────

def test_combined_uses_llm_when_available(monkeypatch):
    fake = fake_anthropic(json.dumps({
        "clusters": [{"summary": "from llm", "representative_quote": "q",
                       "member_indices": [0]}]
    }))
    client = _client_with_fake(monkeypatch, fake)
    out = combined_cluster([_pp(kws=["i wish"])], client=client)
    assert out[0].summary == "from llm"


def test_combined_falls_back_to_heuristic_on_llm_failure(monkeypatch):
    fake = fake_anthropic_raises(Exception("network"))
    client = _client_with_fake(monkeypatch, fake)
    out = combined_cluster([_pp(kws=["i wish"])], client=client)
    # Heuristic groups by keyword
    assert "i wish" in out[0].summary
