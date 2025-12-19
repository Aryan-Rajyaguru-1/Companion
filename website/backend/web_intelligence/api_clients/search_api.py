"""
Web Search API Client
=====================

Search the web using DuckDuckGo and other search engines
"""

import logging
from typing import List, Dict, Any, Optional
import requests
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)


class WebSearchClient:
    """
    Web search client for searching the internet
    
    Features:
    - DuckDuckGo search
    - Zero-click info (instant answers)
    - Related topics
    - No API key required
    """
    
    def __init__(self):
        """Initialize web search client"""
        self.ddg_api = "https://api.duckduckgo.com/"
        self.enabled = True
        logger.info("✅ Web search client initialized")
    
    def search(
        self,
        query: str,
        limit: int = 10,
        safe_search: bool = True
    ) -> Dict[str, Any]:
        """
        Search the web
        
        Args:
            query: Search query
            limit: Number of results
            safe_search: Enable safe search
            
        Returns:
            Search results with instant answer, related topics
        """
        try:
            # DuckDuckGo instant answer API
            params = {
                'q': query,
                'format': 'json',
                'no_html': 1,
                'skip_disambig': 1
            }
            
            response = requests.get(
                self.ddg_api,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                return {
                    'success': True,
                    'query': query,
                    'instant_answer': {
                        'abstract': data.get('Abstract', ''),
                        'abstract_text': data.get('AbstractText', ''),
                        'abstract_source': data.get('AbstractSource', ''),
                        'abstract_url': data.get('AbstractURL', ''),
                        'image': data.get('Image', ''),
                        'heading': data.get('Heading', '')
                    },
                    'related_topics': [
                        {
                            'title': topic.get('Text', ''),
                            'url': topic.get('FirstURL', '')
                        }
                        for topic in data.get('RelatedTopics', [])[:limit]
                        if isinstance(topic, dict) and topic.get('FirstURL')
                    ],
                    'results': data.get('Results', [])[:limit],
                    'answer_type': data.get('AnswerType', ''),
                    'definition': data.get('Definition', ''),
                    'definition_source': data.get('DefinitionSource', ''),
                }
            else:
                logger.error(f"DuckDuckGo API error: {response.status_code}")
                return {'success': False, 'error': 'API error'}
                
        except Exception as e:
            logger.error(f"❌ Search failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_instant_answer(self, query: str) -> Optional[str]:
        """
        Get instant answer for query
        
        Args:
            query: Query to answer
            
        Returns:
            Instant answer text or None
        """
        result = self.search(query, limit=1)
        
        if result.get('success'):
            instant = result.get('instant_answer', {})
            return (
                instant.get('abstract_text') or
                instant.get('abstract') or
                result.get('definition')
            )
        
        return None
    
    def search_related(self, query: str, limit: int = 5) -> List[Dict[str, str]]:
        """
        Get related topics for query
        
        Args:
            query: Search query
            limit: Number of related topics
            
        Returns:
            List of related topics with titles and URLs
        """
        result = self.search(query, limit=limit)
        
        if result.get('success'):
            return result.get('related_topics', [])
        
        return []


# Singleton instance
_search_client = None

def get_search_client() -> WebSearchClient:
    """Get singleton search client instance"""
    global _search_client
    if _search_client is None:
        _search_client = WebSearchClient()
    return _search_client
