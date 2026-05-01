"""CLI entry — `python -m customer_discovery_agent <subcommand>`.

Subcommands:
    scan          Scrape Reddit subreddits, cluster, write markdown digest
    scan-vibex    Pull weaknesses from VibeX ai_reviews, cluster (zero new
                  Claude — re-uses already-paid review text as pain signal)
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

from .cluster import cluster
from .digest import render_markdown
from .reddit_scraper import DEFAULT_PAIN_KEYWORDS, scrape_many
from .types import Digest
from .vibex_reviews_source import scrape_vibex_reviews


def cmd_scan(args) -> int:
    keywords = args.keywords or DEFAULT_PAIN_KEYWORDS
    print(f"🔎 scanning {len(args.subreddits)} subreddit(s) for pain in last "
          f"{args.hours}h (min_score={args.min_score})", file=sys.stderr)
    pain = scrape_many(args.subreddits, hours=args.hours,
                        keywords=keywords, min_score=args.min_score,
                        limit_per_sub=args.limit)
    print(f"   → {len(pain)} matching pain points", file=sys.stderr)

    # If --include-vibex flagged, blend in VibeX ai_reviews weaknesses
    if args.include_vibex:
        vibex_pain = scrape_vibex_reviews(days=args.vibex_days,
                                            limit=args.vibex_limit)
        print(f"   + {len(vibex_pain)} weaknesses from VibeX ai_reviews",
              file=sys.stderr)
        pain = pain + vibex_pain

    clusters = cluster(pain, max_clusters=args.max_clusters)
    sources = ["reddit"]
    if args.include_vibex:
        sources.append("vibex_reviews")
    d = Digest(
        window_hours=args.hours,
        sources=sources,
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


def cmd_scan_vibex(args) -> int:
    """Pure VibeX-only scan — no Reddit. Useful for tracking what your own
    users keep complaining about."""
    print(f"🔨 pulling VibeX ai_reviews weaknesses from last {args.days}d "
          f"(limit {args.limit})", file=sys.stderr)
    pain = scrape_vibex_reviews(days=args.days, limit=args.limit)
    print(f"   → {len(pain)} weaknesses", file=sys.stderr)

    clusters = cluster(pain, max_clusters=args.max_clusters)
    d = Digest(
        window_hours=args.days * 24,
        sources=["vibex_reviews"],
        keywords=[],
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
    s.add_argument("--include-vibex", action="store_true",
                    help="Also pull weaknesses from VibeX ai_reviews "
                         "(needs SUPABASE_PERSONAL_ACCESS_TOKEN + "
                         "VIBEX_PROJECT_REF)")
    s.add_argument("--vibex-days", type=int, default=30,
                    help="Lookback days for VibeX reviews (default 30)")
    s.add_argument("--vibex-limit", type=int, default=200,
                    help="Max VibeX projects to pull (default 200)")
    s.set_defaults(func=cmd_scan)

    v = sub.add_parser("scan-vibex",
                        help="VibeX-only scan: cluster weaknesses from "
                             "ai_reviews (zero new Claude calls)")
    v.add_argument("--days", type=int, default=30)
    v.add_argument("--limit", type=int, default=200)
    v.add_argument("--max-clusters", type=int, default=7)
    v.add_argument("--out", default=None)
    v.set_defaults(func=cmd_scan_vibex)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
