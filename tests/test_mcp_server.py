"""Tests for the customer-discovery MCP server tools."""
from __future__ import annotations
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

mcp_available = True
try:
    from mcp.server.fastmcp import FastMCP  # noqa: F401
except ImportError:
    mcp_available = False

pytestmark = pytest.mark.skipif(not mcp_available,
                                  reason="mcp optional dep not installed")


@pytest.fixture
def mod():
    from customer_discovery_agent import mcp_server
    return mcp_server


def test_scan_empty_subreddits(mod):
    out = mod.scan([])
    assert "at least one subreddit" in out.lower()


def test_keyword_list_returns_keywords(mod):
    out = mod.keyword_list()
    assert "Pain keywords" in out
    # should list multiple bullets
    assert out.count("\n-") >= 5


def test_latest_digest_missing_dir(mod, tmp_path):
    out = mod.latest_digest(str(tmp_path / "missing"))
    assert "not found" in out.lower()


def test_latest_digest_empty_dir(mod, tmp_path):
    out = mod.latest_digest(str(tmp_path))
    assert "no *.md digests" in out.lower()


def test_latest_digest_returns_newest(mod, tmp_path):
    import time
    older = tmp_path / "2026-04-01.md"
    older.write_text("# old\n")
    time.sleep(0.05)
    newer = tmp_path / "2026-04-15.md"
    newer.write_text("# fresh content\n")
    out = mod.latest_digest(str(tmp_path))
    assert "fresh content" in out


def test_main_skips_when_skip_env_set(mod, monkeypatch):
    monkeypatch.setenv("CDA_SKIP", "1")
    with patch.object(mod.mcp, "run") as fake_run:
        mod.main()
    fake_run.assert_not_called()


def test_mcp_instance_is_fastmcp(mod):
    from mcp.server.fastmcp import FastMCP
    assert isinstance(mod.mcp, FastMCP)
