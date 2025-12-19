"""
Web Intelligence Module
========================

Phase 3: Web scraping, API integration, and content processing
"""

from .crawler import WebContentCrawler, get_crawler
from .api_clients import (
    NewsAPIClient,
    get_news_client,
    WebSearchClient,
    get_search_client
)

__all__ = [
    'WebContentCrawler',
    'get_crawler',
    'NewsAPIClient',
    'get_news_client',
    'WebSearchClient',
    'get_search_client',
]
