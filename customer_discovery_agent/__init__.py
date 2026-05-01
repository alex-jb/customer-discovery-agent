"""customer-discovery-agent — scan online communities for maker pain points."""
from .types import Cluster, Digest, PainPoint
from .reddit_scraper import scrape_many, scrape_subreddit, DEFAULT_PAIN_KEYWORDS
from .cluster import cluster, heuristic_cluster, llm_cluster
from .digest import render_markdown
from .vibex_reviews_source import scrape_vibex_reviews

__version__ = "0.5.0"
__all__ = [
    "Cluster", "Digest", "PainPoint",
    "scrape_many", "scrape_subreddit", "DEFAULT_PAIN_KEYWORDS",
    "cluster", "heuristic_cluster", "llm_cluster",
    "render_markdown",
    "scrape_vibex_reviews",
]
