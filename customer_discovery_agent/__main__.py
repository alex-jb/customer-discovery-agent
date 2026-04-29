"""CLI entry — `python -m customer_discovery_agent <subcommand>`.

Subcommands:
    scan      Scrape Reddit subreddits, cluster, write markdown digest
"""
from __future__ import annotations
import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .cluster import cluster
from .digest import render_markdown
from .reddit_scraper import DEFAULT_PAIN_KEYWORDS, scrape_many
from .types import Digest


def cmd_scan(args) -> int:
    keywords = args.keywords or DEFAULT_PAIN_KEYWORDS
    print(f"🔎 scanning {len(args.subreddits)} subreddit(s) for pain in last "
          f"{args.hours}h (min_score={args.min_score})", file=sys.stderr)
    pain = scrape_many(args.subreddits, hours=args.hours,
                        keywords=keywords, min_score=args.min_score,
                        limit_per_sub=args.limit)
    print(f"   → {len(pain)} matching pain points", file=sys.stderr)

    clusters = cluster(pain, max_clusters=args.max_clusters)
    d = Digest(
        window_hours=args.hours,
        sources=["reddit"],
        keywords=keywords,
        n_pain_points=len(pain),
        clusters=clusters,
    )

    md = render_markdown(d)
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"📄 digest written: {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(md)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="customer-discovery-agent",
        description="Scan online communities for maker pain points; "
                     "cluster into a weekly digest.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="Scrape + cluster + render digest")
    s.add_argument("--subreddits", nargs="+", required=True,
                    help="e.g. SaaS IndieHackers SideProject Entrepreneur")
    s.add_argument("--hours", type=int, default=168,
                    help="Lookback window (default 168h = 1 week)")
    s.add_argument("--keywords", nargs="*", default=None,
                    help="Pain-pattern keywords (default: built-in list of 17)")
    s.add_argument("--min-score", type=int, default=5,
                    help="Skip posts with fewer upvotes than this")
    s.add_argument("--limit", type=int, default=100,
                    help="Max posts to scan per subreddit per stream")
    s.add_argument("--max-clusters", type=int, default=7)
    s.add_argument("--out", default=None,
                    help="Write digest markdown to this path (default: stdout)")
    s.set_defaults(func=cmd_scan)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
