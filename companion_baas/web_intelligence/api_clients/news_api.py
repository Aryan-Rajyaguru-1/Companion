"""
News API Client
===============

Fetch news from multiple sources
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import requests

logger = logging.getLogger(__name__)


class NewsAPIClient:
    """
    News aggregator from multiple sources
    
    Features:
    - Multiple news sources
    - Category filtering
    - Keyword search
    - Date range filtering
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize news API client
        
        Args:
            api_key: NewsAPI.org API key (optional)
        """
        self.api_key = api_key
        self.base_url = "https://newsapi.org/v2"
        self.enabled = api_key is not None
        
        if not self.enabled:
            logger.info("NewsAPI key not provided - using free sources")
    
    def get_top_headlines(
        self,
        category: Optional[str] = None,
        country: str = "us",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get top headlines
        
        Args:
            category: News category (business, tech, sports, etc.)
            country: Country code (us, gb, in, etc.)
            limit: Number of articles
            
        Returns:
            List of news articles
        """
        if not self.enabled:
            return self._get_free_news(category, limit)
        
        try:
            params = {
                'apiKey': self.api_key,
                'country': country,
                'pageSize': limit
            }
            
            if category:
                params['category'] = category
            
            response = requests.get(
                f"{self.base_url}/top-headlines",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return self._format_articles(data.get('articles', []))
            else:
                logger.error(f"NewsAPI error: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Failed to fetch news: {e}")
            return []
    
    def search_news(
        self,
        query: str,
        from_date: Optional[datetime] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search news by keyword
        
        Args:
            query: Search query
            from_date: Start date for results
            limit: Number of results
            
        Returns:
            List of news articles
        """
        if not self.enabled:
            return self._get_free_news(query, limit)
        
        try:
            params = {
                'apiKey': self.api_key,
                'q': query,
                'sortBy': 'publishedAt',
                'pageSize': limit
            }
            
            if from_date:
                params['from'] = from_date.isoformat()
            
            response = requests.get(
                f"{self.base_url}/everything",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return self._format_articles(data.get('articles', []))
            else:
                logger.error(f"NewsAPI search error: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Failed to search news: {e}")
            return []
    
    def _format_articles(self, articles: List[Dict]) -> List[Dict[str, Any]]:
        """Format articles to standard structure"""
        formatted = []
        
        for article in articles:
            formatted.append({
                'title': article.get('title', ''),
                'description': article.get('description', ''),
                'url': article.get('url', ''),
                'source': article.get('source', {}).get('name', 'Unknown'),
                'published_at': article.get('publishedAt', ''),
                'author': article.get('author', 'Unknown'),
                'image_url': article.get('urlToImage'),
                'content': article.get('content', ''),
                'timestamp': datetime.utcnow().isoformat()
            })
        
        return formatted
    
    def _get_free_news(self, query: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get news from free sources (fallback)
        
        Args:
            query: Optional search query
            limit: Number of articles
            
        Returns:
            List of news articles
        """
        # TODO: Implement free news scraping from RSS feeds
        logger.info("Using free news sources (limited data)")
        
        # Sample data for demonstration
        return [
            {
                'title': 'AI Technology Advances Continue',
                'description': 'Latest developments in artificial intelligence and machine learning',
                'url': 'https://example.com/ai-news',
                'source': 'Tech News',
                'published_at': datetime.utcnow().isoformat(),
                'author': 'Tech Reporter',
                'image_url': None,
                'content': 'Sample content about AI advances...',
                'timestamp': datetime.utcnow().isoformat()
            }
        ][:limit]


# Singleton instance
_news_client = None

def get_news_client(api_key: Optional[str] = None) -> NewsAPIClient:
    """Get singleton news client instance"""
    global _news_client
    if _news_client is None:
        _news_client = NewsAPIClient(api_key)
    return _news_client
