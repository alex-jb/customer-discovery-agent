"""Reddit pain-point scraper.

Why Reddit first? Of the 5 sources in the v0.2 backlog (Reddit / IndieHackers
/ X / 即刻 / 知乎), Reddit has the cleanest API (PRAW) AND the densest
maker-pain content per dollar. Solo founders disproportionately complain
on r/SaaS, r/IndieHackers, r/Entrepreneur, r/SideProject.

This module:
  1. Lists `top` and `new` posts in configured subreddits over `hours`
  2. Filters by pain-pattern keywords (default list tuned for SaaS/AI dev pain)
  3. Returns a list of PainPoint dicts, deduped by source_id

Auth: PRAW script app via 5 env vars (same shape as marketing-agent's
Reddit adapter). Without them, returns []. No-op-friendly.
"""
from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone

from .types import PainPoint


# Default pain-pattern keywords — tuned to surface "I have problem X" posts.
# Tweakable via CLI --keywords.
DEFAULT_PAIN_KEYWORDS = [
    "i wish", "i need", "looking for a tool", "is there a", "anyone use",
    "frustrated", "struggle with", "spent hours", "wasted", "stuck on",
    "doesn't work", "no good way", "best way to", "alternative to",
    "any way to", "how do you", "tired of",
]


def _has_pain_match(text: str, keywords: list[str]) -> list[str]:
    """Return the subset of keywords that appear in `text` (case-insensitive)."""
    low = text.lower()
    return [k for k in keywords if k in low]


def is_configured() -> bool:
    return all(os.getenv(k) for k in (
        "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
        "REDDIT_USERNAME", "REDDIT_PASSWORD", "REDDIT_USER_AGENT",
    ))


def scrape_subreddit(subreddit: str, *, hours: int = 168,
                       keywords: list[str] | None = None,
                       min_score: int = 5,
                       limit: int = 100) -> list[PainPoint]:
    """Scrape one subreddit. Returns [] if PRAW isn't configured.

    `hours` of lookback (default 1 week). Posts older than that are skipped.
    """
    if not is_configured():
        return []
    try:
        import praw
    except ImportError:
        return []

    kw = keywords or DEFAULT_PAIN_KEYWORDS
    cutoff_ts = (datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp()

    reddit = praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        username=os.getenv("REDDIT_USERNAME"),
        password=os.getenv("REDDIT_PASSWORD"),
        user_agent=os.getenv("REDDIT_USER_AGENT"),
    )

    out: list[PainPoint] = []
    seen: set[str] = set()
    sub = reddit.subreddit(subreddit)

    for stream in (sub.new(limit=limit), sub.top(time_filter="week", limit=limit)):
        for s in stream:
            if s.id in seen:
                continue
            if s.created_utc < cutoff_ts:
                continue
            if s.score < min_score:
                continue
            text = f"{s.title}\n{s.selftext or ''}"
            matched = _has_pain_match(text, kw)
            if not matched:
                continue
            seen.add(s.id)
            out.append(PainPoint(
                source="reddit",
                source_id=f"reddit/{s.id}",
                url=f"https://reddit.com{s.permalink}",
                title=s.title[:300],
                body=(s.selftext or "")[:2000],
                author=str(s.author) if s.author else "[deleted]",
                score=int(s.score),
                n_comments=int(s.num_comments),
                created_at=datetime.fromtimestamp(s.created_utc, tz=timezone.utc),
                keywords_matched=matched,
            ))
    return out


def scrape_many(subreddits: list[str], *, hours: int = 168,
                 keywords: list[str] | None = None,
                 min_score: int = 5,
                 limit_per_sub: int = 100) -> list[PainPoint]:
    """Scrape multiple subreddits, dedup across them, return all pain points."""
    seen: set[str] = set()
    out: list[PainPoint] = []
    for sub in subreddits:
        for pp in scrape_subreddit(
            sub, hours=hours, keywords=keywords,
            min_score=min_score, limit=limit_per_sub,
        ):
            if pp.source_id in seen:
                continue
            seen.add(pp.source_id)
            out.append(pp)
    return out
