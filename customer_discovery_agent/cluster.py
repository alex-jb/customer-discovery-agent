"""Cluster pain points into themes.

Two modes:
  1. **LLM mode** (when ANTHROPIC_API_KEY set): one Claude Haiku call clusters
     all pain points into 3-7 themes with summary + representative quote.
  2. **Heuristic fallback**: keyword-based grouping using the matched pain
     phrases as cluster anchors. Cheaper, deterministic, less coherent.

The output is small (3-7 clusters with ≤5 sample URLs each), so the digest
fits in a single email or markdown report.

v0.2: LLM call goes through solo_founder_os.AnthropicClient — token usage
auto-logged to ~/.customer-discovery-agent/usage.jsonl. cost-audit-agent
picks it up in monthly reports.
"""
from __future__ import annotations
import json
import pathlib
from collections import defaultdict
from typing import Optional

from solo_founder_os.anthropic_client import (
    AnthropicClient,
    DEFAULT_HAIKU_MODEL,
)

from .types import Cluster, PainPoint


USAGE_LOG_PATH = (pathlib.Path.home()
                  / ".customer-discovery-agent" / "usage.jsonl")


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


CLUSTER_SCHEMA = {
    "type": "object",
    "properties": {
        "clusters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "representative_quote": {"type": "string"},
                    "member_indices": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                },
                "required": ["summary", "representative_quote", "member_indices"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["clusters"],
    "additionalProperties": False,
}


def llm_cluster(pain_points: list[PainPoint],
                 max_clusters: int = 7,
                 *, client: AnthropicClient | None = None) -> Optional[list[Cluster]]:
    """Use Claude Haiku to cluster. Returns None on any failure.

    `client` is injectable for tests. In production, leave it None and the
    function constructs an AnthropicClient pointed at the CDA usage log.

    v0.3: uses solo_founder_os.messages_create_json — guaranteed valid JSON
    output. Eliminates the markdown-fence-stripping + json.loads-with-fallback
    path that v0.2 had.
    """
    if not pain_points:
        return []

    if client is None:
        client = AnthropicClient(usage_log_path=USAGE_LOG_PATH)

    if not client.configured:
        return None

    # Pack the list as a numbered list for the model
    snippets = []
    for i, pp in enumerate(pain_points[:200]):  # cap at 200 to stay under token budget
        body_excerpt = (pp.body or "")[:300].replace("\n", " ")
        snippets.append(f"[{i}] r/{pp.url.split('/r/')[-1].split('/')[0]} "
                          f"({pp.score} upvotes): {pp.title} — {body_excerpt}")

    prompt = (
        f"You are clustering {len(snippets)} maker pain points. Group into "
        f"{max_clusters} or fewer themes. Output JSON conforming to the schema:\n"
        f"  clusters: array of {{summary, representative_quote, member_indices}}\n"
        f"Each summary ≤ 80 chars. representative_quote is a verbatim ≤120-char "
        f"excerpt from one of the member posts. member_indices are 0-based "
        f"into the input list.\n\nInput:\n" + "\n".join(snippets)
    )

    data, err = client.messages_create_json(
        schema=CLUSTER_SCHEMA,
        model=DEFAULT_HAIKU_MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    if err is not None or data is None:
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
    # L3 skill library: record this clustering as a successful LLM example.
    # Inputs are the high-level shape (n pain points, source mix), not the
    # raw text — keeps the example file compact + privacy-safe.
    if out:
        try:
            from solo_founder_os import record_example
            sources = sorted({pp.source for pp in pain_points})
            record_example(
                "cluster-pain-points",
                inputs={
                    "n_pain_points": len(pain_points),
                    "max_clusters": max_clusters,
                    "sources": ",".join(sources),
                },
                output=json.dumps(
                    [{"summary": c.summary, "n_posts": c.n_posts}
                     for c in out],
                    ensure_ascii=False),
                note=f"LLM produced {len(out)} clusters",
            )
        except Exception:
            pass
    return out


def cluster(pain_points: list[PainPoint],
              max_clusters: int = 7,
              *, client: AnthropicClient | None = None) -> list[Cluster]:
    """Combined: try LLM, fall back to heuristic.

    `client` is forwarded to llm_cluster — pass a pre-loaded
    AnthropicClient in tests, leave None in production.
    """
    llm = llm_cluster(pain_points, max_clusters=max_clusters, client=client)
    if llm is not None:
        return llm
    # Reflexion: heuristic fallback means LLM was unavailable or returned
    # garbage. Log so future runs can adapt prompts. Best-effort.
    if pain_points:
        try:
            from solo_founder_os import log_outcome
            log_outcome(".customer-discovery-agent", task="cluster",
                        outcome="PARTIAL",
                        signal=("LLM cluster returned None — fell back to "
                                "heuristic keyword grouping"))
        except Exception:
            pass
    return heuristic_cluster(pain_points, max_clusters=max_clusters)
