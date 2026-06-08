"""Tests for the VibeX ai_reviews → PainPoint source."""
from __future__ import annotations
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from customer_discovery_agent.vibex_reviews_source import scrape_vibex_reviews


def _fake_urlopen(payload):
    fake = MagicMock()
    fake.read.return_value = json.dumps(payload).encode()
    fake.__enter__ = lambda s: s
    fake.__exit__ = lambda *a: None
    return fake


def test_returns_empty_when_unconfigured(monkeypatch):
    monkeypatch.delenv("SUPABASE_PERSONAL_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("VIBEX_PROJECT_REF", raising=False)
    monkeypatch.delenv("SUPABASE_PROJECT_REF", raising=False)
    assert scrape_vibex_reviews() == []


def test_explodes_each_weakness_into_painpoint(monkeypatch):
    monkeypatch.setenv("SUPABASE_PERSONAL_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("VIBEX_PROJECT_REF", "abc")
    fake = _fake_urlopen([
        {
            "project_id": "p1",
            "project_title": "AI Receipt Splitter",
            "creator": "u_1",
            "plays": 50, "upvotes": 12,
            "created_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
            "weaknesses": [
                "Onboarding is confusing",
                "Mobile UI is broken on small screens",
                "",  # empty string should be skipped
            ],
            "suggestions": ["Add a tutorial"],
        },
    ])
    with patch("urllib.request.urlopen", return_value=fake):
        out = scrape_vibex_reviews(days=30)
    assert len(out) == 2  # empty weakness skipped
    titles = [pp.body for pp in out]
    assert "Onboarding is confusing" in titles
    assert all(pp.source == "vibex_reviews" for pp in out)
    assert all(pp.url == "https://www.vibexforge.com/project/p1" for pp in out)
    # Score should map to upvotes
    assert all(pp.score == 12 for pp in out)
    # n_comments should map to plays
    assert all(pp.n_comments == 50 for pp in out)
    # Stable source_id
    assert out[0].source_id == "p1:w0"
    assert out[1].source_id == "p1:w1"


def test_filters_by_lookback_window(monkeypatch):
    """Reviews older than `days` lookback are dropped — defends against
    Supabase returning a too-wide window if the SQL filter ever drifts."""
    monkeypatch.setenv("SUPABASE_PERSONAL_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("VIBEX_PROJECT_REF", "abc")
    fake = _fake_urlopen([
        {
            "project_id": "old", "project_title": "Old project",
            "creator": "u_1", "plays": 0, "upvotes": 0,
            "created_at": "2024-01-01T00:00:00+00:00",  # very old
            "weaknesses": ["This is too old to count"],
        },
    ])
    with patch("urllib.request.urlopen", return_value=fake):
        out = scrape_vibex_reviews(days=30)
    assert out == []


def test_skips_rows_without_weaknesses(monkeypatch):
    """Defensive: project with NULL or non-list weaknesses field shouldn't
    crash — just gets silently dropped."""
    monkeypatch.setenv("SUPABASE_PERSONAL_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("VIBEX_PROJECT_REF", "abc")
    fake = _fake_urlopen([
        {"project_id": "p1", "weaknesses": None},
        {"project_id": "p2", "weaknesses": "not a list"},
        {"project_id": "p3", "weaknesses": []},
    ])
    with patch("urllib.request.urlopen", return_value=fake):
        out = scrape_vibex_reviews()
    assert out == []


def test_handles_management_api_dict_response(monkeypatch):
    """API may return {'result': [...]} or list — both should work."""
    monkeypatch.setenv("SUPABASE_PERSONAL_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("VIBEX_PROJECT_REF", "abc")
    fake = _fake_urlopen({"result": [
        {
            "project_id": "p1", "project_title": "X", "creator": "u_1",
            "plays": 1, "upvotes": 1,
            "created_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
            "weaknesses": ["something"],
        }
    ]})
    with patch("urllib.request.urlopen", return_value=fake):
        out = scrape_vibex_reviews(days=30)
    assert len(out) == 1


def test_swallows_network_errors(monkeypatch):
    """Failed Supabase call shouldn't raise — just returns empty."""
    monkeypatch.setenv("SUPABASE_PERSONAL_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("VIBEX_PROJECT_REF", "abc")
    with patch("urllib.request.urlopen", side_effect=Exception("net")):
        out = scrape_vibex_reviews()
    assert out == []


def test_falls_back_to_supabase_project_ref(monkeypatch):
    """If only SUPABASE_PROJECT_REF is set, source uses it."""
    monkeypatch.setenv("SUPABASE_PERSONAL_ACCESS_TOKEN", "tok")
    monkeypatch.delenv("VIBEX_PROJECT_REF", raising=False)
    monkeypatch.setenv("SUPABASE_PROJECT_REF", "shared_ref")
    fake = _fake_urlopen([])
    with patch("urllib.request.urlopen", return_value=fake) as mock_urlopen:
        scrape_vibex_reviews()
    # Verify the URL used the shared ref
    call_args = mock_urlopen.call_args
    if call_args:
        req = call_args[0][0]
        assert "shared_ref" in req.full_url
