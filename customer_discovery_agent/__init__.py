"""customer-discovery-agent — scan online communities for maker pain points."""
from .types import Cluster, Digest, PainPoint
from .reddit_scraper import scrape_many, scrape_subreddit, DEFAULT_PAIN_KEYWORDS
from .cluster import cluster, heuristic_cluster, llm_cluster
from .digest import render_markdown

__version__ = "0.4.0"
__all__ = [
    "Cluster", "Digest", "PainPoint",
    "scrape_many", "scrape_subreddit", "DEFAULT_PAIN_KEYWORDS",
    "cluster", "heuristic_cluster", "llm_cluster",
    "render_markdown",
]
