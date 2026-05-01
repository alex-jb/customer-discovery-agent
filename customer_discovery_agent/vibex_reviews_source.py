"""VibeX `ai_reviews` table → PainPoint stream.

Why: VibeX already runs Claude on every project that gets forged, producing
a 5-dim review with `weaknesses[]` and `suggestions[]`. Each weakness is
a real-user-tested pain signal — much higher fidelity than Reddit
keyword scraping. Re-using these reviews as a CDA data source costs $0
in new API calls (the Claude review already happened on the VibeX side).

Each weakness string from `ai_reviews.weaknesses` becomes one PainPoint.
Project metadata (title, score, plays) gives us PainPoint.score so the
cluster picks high-traffic projects' weaknesses as representative quotes.

Auth: SUPABASE_PERSONAL_ACCESS_TOKEN (project-wide); VIBEX_PROJECT_REF
(or fall back to SUPABASE_PROJECT_REF for the common one-project case).
"""
from __future__ import annotations
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from .types import PainPoint


VIBEX_REVIEWS_SQL = """
SELECT
  p.id           AS project_id,
  p.title        AS project_title,
  p.creator_id   AS creator,
  p.plays        AS plays,
  p.upvotes      AS upvotes,
  p.created_at   AS created_at,
  r.weaknesses   AS weaknesses,
  r.suggestions  AS suggestions
FROM ai_reviews r
JOIN projects p ON p.id = r.project_id
WHERE p.created_at >= now() - interval '%(days)s days'
  AND r.weaknesses IS NOT NULL
  AND array_length(r.weaknesses, 1) > 0
ORDER BY p.upvotes DESC, p.plays DESC
LIMIT %(limit)s
""".strip()


def _query(sql: str, *, token: str, project_ref: str) -> list[dict]:
    """Hit Supabase Management API SQL endpoint. Same shape funnel uses."""
    url = f"https://api.supabase.com/v1/projects/{project_ref}/database/query"
    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Authorization": f"Bearer {token}",
                  "Content-Type": "application/json",
                  "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode())
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("result", "rows", "data"):
            if key in data and isinstance(data[key], list):
                return data[key]
    return []


def scrape_vibex_reviews(
    *,
    days: int = 30,
    limit: int = 200,
    project_ref: str | None = None,
    token: str | None = None,
) -> list[PainPoint]:
    """Pull recent VibeX project reviews and explode each weakness into a PainPoint.

    `days` controls the lookback window; default 30 covers the soft-launch
    + PH-day + first week. `limit` caps row count to keep clustering cheap.
    """
    token = token or os.getenv("SUPABASE_PERSONAL_ACCESS_TOKEN") or ""
    project_ref = (project_ref or os.getenv("VIBEX_PROJECT_REF")
                    or os.getenv("SUPABASE_PROJECT_REF") or "")
    if not token or not project_ref:
        return []

    sql = VIBEX_REVIEWS_SQL % {"days": int(days), "limit": int(limit)}
    try:
        rows = _query(sql, token=token, project_ref=project_ref)
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, TimeoutError):
        return []
    except Exception:
        return []

    out: list[PainPoint] = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    for row in rows:
        weaknesses = row.get("weaknesses") or []
        if not isinstance(weaknesses, list):
            continue
        # Parse created_at; fallback to now() so the row still surfaces
        ts = row.get("created_at")
        try:
            created = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except Exception:
            created = datetime.now(timezone.utc)
        if created < cutoff:
            continue
        project_id = row.get("project_id") or ""
        title = row.get("project_title") or "(untitled)"
        plays = int(row.get("plays") or 0)
        upvotes = int(row.get("upvotes") or 0)
        # PainPoint.score = upvotes (closest analog to Reddit upvotes on VibeX)
        for i, weakness in enumerate(weaknesses):
            text = (weakness or "").strip()
            if not text:
                continue
            out.append(PainPoint(
                source="vibex_reviews",
                source_id=f"{project_id}:w{i}",
                url=f"https://www.vibexforge.com/project/{project_id}",
                title=title,
                body=text,
                author=row.get("creator") or "vibex_creator",
                score=upvotes,
                n_comments=plays,  # approximate engagement signal
                created_at=created,
                keywords_matched=[],  # weaknesses are *the* signal, no keyword filter needed
            ))
    return out
