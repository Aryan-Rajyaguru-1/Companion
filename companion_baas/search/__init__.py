"""
Search Layer - Fast Text & Semantic Search
==========================================

Provides unified search interface combining:
- Meilisearch: Fast full-text search (<50ms)
- Elasticsearch: Semantic vector search
- Hybrid Search: Best of both worlds
"""

from .meilisearch_client import MeilisearchClient, get_meilisearch_client
from .search_engine import SearchEngine, get_search_engine

__all__ = [
    'MeilisearchClient',
    'get_meilisearch_client',
    'SearchEngine',
    'get_search_engine'
]
