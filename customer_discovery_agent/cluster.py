"""Cluster pain points into themes.

Two modes:
  1. **LLM mode** (when ANTHROPIC_API_KEY set): one Claude Haiku call clusters
     all pain points into 3-7 themes with summary + representative quote.
  2. **Heuristic fallback**: keyword-based grouping using the matched pain
     phrases as cluster anchors. Cheaper, deterministic, less coherent.

The output is small (3-7 clusters with ≤5 sample URLs each), so the digest
fits in a single email or markdown report.
"""
from __future__ import annotations
import json
import os
import re
from collections import defaultdict
from typing import Optional

from .types import Cluster, PainPoint


def heuristic_cluster(pain_points: list[PainPoint],
                        max_clusters: int = 7) -> list[Cluster]:
    """Group by the most common matched-keyword. No LLM call."""
    if not pain_points:
        return []
    by_kw: dict[str, list[PainPoint]] = defaultdict(list)
    for pp in pain_points:
        if not pp.keywords_matched:
            by_kw["(uncategorized)"].append(pp)
            continue
        # Use the first matched keyword as the cluster anchor
        by_kw[pp.keywords_matched[0]].append(pp)

    # Sort by cluster size, take top N
    items = sorted(by_kw.items(), key=lambda kv: len(kv[1]), reverse=True)
    out: list[Cluster] = []
    for i, (kw, group) in enumerate(items[:max_clusters]):
        # Pick highest-scored post as representative
        top = max(group, key=lambda p: p.score)
        avg = sum(p.score for p in group) / len(group)
        out.append(Cluster(
            cluster_id=f"c{i}",
            summary=f"Posts mentioning \"{kw}\"",
            representative_quote=top.title[:200],
            n_posts=len(group),
            avg_score=round(avg, 1),
            sample_urls=[p.url for p in
                          sorted(group, key=lambda p: p.score, reverse=True)[:5]],
        ))
    return out


def llm_cluster(pain_points: list[PainPoint],
                 max_clusters: int = 7) -> Optional[list[Cluster]]:
    """Use Claude Haiku to cluster. Returns None on any failure."""
    if not pain_points:
        return []
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        from anthropic import Anthropic
    except ImportError:
        return None

    # Pack the list as a numbered list for the model
    snippets = []
    for i, pp in enumerate(pain_points[:200]):  # cap at 200 to stay under token budget
        body_excerpt = (pp.body or "")[:300].replace("\n", " ")
        snippets.append(f"[{i}] r/{pp.url.split('/r/')[-1].split('/')[0]} "
                          f"({pp.score} upvotes): {pp.title} — {body_excerpt}")

    prompt = (
        f"You are clustering {len(snippets)} maker pain points. Group into "
        f"{max_clusters} or fewer themes. Output STRICT JSON of shape:\n"
        f"{{\"clusters\": [{{\"summary\": \"...\", \"representative_quote\": "
        f"\"...\", \"member_indices\": [0, 5, 12]}}]}}\n\n"
        f"Each summary ≤ 80 chars. representative_quote is a verbatim ≤120-char "
        f"excerpt from one of the member posts. member_indices are 0-based "
        f"into the input list.\n\nInput:\n" + "\n".join(snippets)
    )

    try:
        client = Anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5", max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text).strip()
        data = json.loads(text)
    except Exception:
        return None

    out: list[Cluster] = []
    for i, c in enumerate(data.get("clusters", [])[:max_clusters]):
        member_idx = [j for j in c.get("member_indices", []) if 0 <= j < len(pain_points)]
        if not member_idx:
            continue
        members = [pain_points[j] for j in member_idx]
        out.append(Cluster(
            cluster_id=f"c{i}",
            summary=c.get("summary", "")[:120],
            representative_quote=c.get("representative_quote", "")[:200],
            n_posts=len(members),
            avg_score=round(sum(m.score for m in members) / len(members), 1),
            sample_urls=[m.url for m in
                          sorted(members, key=lambda p: p.score, reverse=True)[:5]],
        ))
    return out


def cluster(pain_points: list[PainPoint],
              max_clusters: int = 7) -> list[Cluster]:
    """Combined: try LLM, fall back to heuristic."""
    llm = llm_cluster(pain_points, max_clusters=max_clusters)
    if llm is not None:
        return llm
    return heuristic_cluster(pain_points, max_clusters=max_clusters)
