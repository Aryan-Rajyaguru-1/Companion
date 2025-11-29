"""
API Clients Module
==================

Public API integrations for news, weather, search, and more
"""

from .news_api import NewsAPIClient, get_news_client
from .search_api import WebSearchClient, get_search_client

__all__ = [
    'NewsAPIClient',
    'get_news_client',
    'WebSearchClient',
    'get_search_client',
]
