"""MCP server — expose customer-discovery scanning to Claude Desktop /
Cursor / Zed. Ask "scan IndieHackers for pain points this week" and the
assistant runs a Reddit scrape, clusters with Claude, returns markdown.

Tools:
  - scan(subreddits, hours=168, max_clusters=7)
        Scrape + cluster + return digest markdown
  - latest_digest(directory)
        Read the most recent digest file from a directory
  - keyword_list()
        Show the built-in pain-pattern keywords

Install:
    pip install customer-discovery-agent[mcp]

Wire to Claude Desktop:

    {
      "mcpServers": {
        "customer-discovery": {
          "command": "customer-discovery-mcp",
          "env": { "ANTHROPIC_API_KEY": "..." }
        }
      }
    }
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:
    print("customer-discovery-mcp requires the `mcp` package. "
          "Install with: pip install 'customer-discovery-agent[mcp]'",
          file=sys.stderr)
    raise SystemExit(1) from e

from .cluster import cluster as cluster_fn
from .digest import render_markdown
from .reddit_scraper import DEFAULT_PAIN_KEYWORDS, scrape_many
from .types import Digest


mcp = FastMCP("customer-discovery")


@mcp.tool()
def scan(subreddits: list[str],
          hours: int = 168,
          min_score: int = 5,
          limit_per_sub: int = 100,
          max_clusters: int = 7) -> str:
    """Scrape one or more subreddits for maker pain points, cluster with
    Claude (or heuristic fallback), return the markdown digest.

    Args:
        subreddits: list of subreddit names without r/ prefix
                    e.g. ["SaaS", "IndieHackers", "SideProject"]
        hours: lookback window (default 168 = 1 week)
        min_score: skip posts with fewer upvotes than this
        limit_per_sub: max posts to scan per subreddit per stream
        max_clusters: target cluster count (3-7 is ideal)
    """
    if not subreddits:
        return "Provide at least one subreddit name."
    pain = scrape_many(subreddits, hours=hours,
                        keywords=DEFAULT_PAIN_KEYWORDS,
                        min_score=min_score,
                        limit_per_sub=limit_per_sub)
    clusters = cluster_fn(pain, max_clusters=max_clusters)
    d = Digest(
        window_hours=hours,
        sources=["reddit"],
        keywords=DEFAULT_PAIN_KEYWORDS,
        n_pain_points=len(pain),
        clusters=clusters,
    )
    return render_markdown(d)


@mcp.tool()
def latest_digest(directory: str = "~/Documents/customer-discovery") -> str:
    """Return the contents of the most recently modified digest file in a
    directory. Useful when you've been writing weekly digests via cron and
    want to ask Claude about the latest one.

    Args:
        directory: directory holding *.md digests (default
                   ~/Documents/customer-discovery)
    """
    p = Path(directory).expanduser()
    if not p.exists():
        return f"Directory not found: {p}"
    files = sorted(p.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        return f"No *.md digests in {p}"
    return files[0].read_text(encoding="utf-8")


@mcp.tool()
def keyword_list() -> str:
    """Return the built-in pain-pattern keyword list — useful before
    launching a custom scan."""
    return "Pain keywords:\n" + "\n".join(f"- {k}" for k in DEFAULT_PAIN_KEYWORDS)


def main() -> None:
    """Console-script entry point. Runs the MCP server over stdio."""
    if os.getenv("CDA_SKIP") == "1":
        return
    mcp.run()


if __name__ == "__main__":
    main()
