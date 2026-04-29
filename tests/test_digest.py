"""Tests for digest.py — markdown rendering."""
from __future__ import annotations
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from customer_discovery_agent.digest import render_markdown
from customer_discovery_agent.types import Cluster, Digest


def _digest(clusters=None, n_pp=0):
    return Digest(
        generated_at=datetime.now(timezone.utc),
        window_hours=168, sources=["reddit"],
        keywords=["i wish"], n_pain_points=n_pp,
        clusters=clusters or [],
    )


def test_renders_header_and_metadata():
    md = render_markdown(_digest(n_pp=42))
    assert "# Customer Discovery Digest" in md
    assert "168h" in md
    assert "reddit" in md
    assert "**42**" in md


def test_renders_no_data_message_when_empty():
    md = render_markdown(_digest())
    assert "no pain points matched" in md.lower()


def test_renders_cluster_with_sample_urls():
    c = Cluster(
        cluster_id="c0",
        summary="Launch tooling friction",
        representative_quote="I wish PH had a preview",
        n_posts=5,
        avg_score=42.0,
        sample_urls=["https://reddit.com/x", "https://reddit.com/y"],
    )
    md = render_markdown(_digest(clusters=[c], n_pp=5))
    assert "### Launch tooling friction" in md
    assert "**5 posts · avg score 42.0**" in md
    assert "> I wish PH had a preview" in md
    assert "- https://reddit.com/x" in md
    assert "- https://reddit.com/y" in md


def test_footer_links_to_repo():
    md = render_markdown(_digest())
    assert "github.com/alex-jb/customer-discovery-agent" in md
