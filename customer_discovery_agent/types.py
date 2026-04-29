"""Core types — Pydantic models passed between modules."""
from __future__ import annotations
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PainPoint(BaseModel):
    """A scraped post / comment that may indicate a real user problem."""
    source: str = Field(..., description="reddit | indiehackers | x | jike | zhihu")
    source_id: str = Field(..., description="Stable id within the source")
    url: str
    title: str
    body: str
    author: str
    score: int = Field(0, description="upvotes / likes / etc.")
    n_comments: int = 0
    created_at: datetime
    keywords_matched: list[str] = Field(default_factory=list)
    cluster_id: Optional[str] = None
    cluster_summary: Optional[str] = None


class Cluster(BaseModel):
    """A group of pain points sharing a theme. Output of LLM clustering."""
    cluster_id: str
    summary: str = Field(..., description="One-line description of the theme")
    representative_quote: str = Field(..., description="Best illustrative excerpt")
    n_posts: int
    avg_score: float
    sample_urls: list[str] = Field(default_factory=list, max_length=5)


class Digest(BaseModel):
    """A weekly digest — top clusters + raw count of pain points scanned."""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    window_hours: int
    sources: list[str]
    keywords: list[str]
    n_pain_points: int
    clusters: list[Cluster] = Field(default_factory=list)
