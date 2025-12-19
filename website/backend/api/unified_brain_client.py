#!/usr/bin/env python3
"""
Unified Brain API Client
=========================

Python client for the Unified Brain REST API.

Usage:
    from api.unified_brain_client import UnifiedBrainClient
    
    client = UnifiedBrainClient("http://localhost:8000")
    
    # Think
    response = client.think("What is Python?")
    
    # Execute code
    result = client.execute_code("print('Hello!')")
    
    # Call tools
    result = client.call_tool("add", 42, 58)
"""

import requests
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class UnifiedBrainClient:
    """
    Client for interacting with the Unified Brain API
    
    This client provides convenient methods for all API endpoints.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Initialize the client
        
        Args:
            base_url: Base URL of the API server
        """
        self.base_url = base_url.rstrip('/')
        self.api_base = f"{self.base_url}/api/v1"
        self.session = requests.Session()
    
    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make HTTP request"""
        url = f"{self.api_base}{endpoint}"
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=params)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data)
            elif method.upper() == "DELETE":
                response = self.session.delete(url)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # ========================================================================
    # CORE METHODS
    # ========================================================================
    
    def think(
        self,
        message: str,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        use_knowledge: bool = False,
        use_search: bool = False,
        use_tools: bool = False,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Main thinking method
        
        Args:
            message: User's input message
            user_id: User identifier
            conversation_id: Conversation identifier
            use_knowledge: Use knowledge base (Phase 1)
            use_search: Use hybrid search (Phase 2)
            use_tools: Allow tool calling (Phase 4)
            context: Additional context
            
        Returns:
            Response dict with 'success', 'response', 'metadata'
        """
        data = {
            'message': message,
            'user_id': user_id,
            'conversation_id': conversation_id,
            'use_knowledge': use_knowledge,
            'use_search': use_search,
            'use_tools': use_tools,
            'context': context
        }
        
        return self._request('POST', '/think', data=data)
    
    def execute_code(
        self,
        code: str,
        language: Optional[str] = None,
        timeout: int = 10
    ) -> Dict[str, Any]:
        """
        Execute code (Phase 4)
        
        Args:
            code: Code to execute
            language: Programming language (python/javascript)
            timeout: Execution timeout in seconds
            
        Returns:
            Execution result with 'success', 'output', 'error', 'execution_time'
        """
        data = {
            'code': code,
            'language': language,
            'timeout': timeout
        }
        
        return self._request('POST', '/execute', data=data)
    
    def call_tool(
        self,
        tool_name: str,
        *args,
        use_cache: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Call a tool (Phase 4)
        
        Args:
            tool_name: Name of the tool
            *args: Positional arguments
            use_cache: Use caching
            **kwargs: Keyword arguments
            
        Returns:
            Tool result with 'success', 'result', 'cached'
        """
        data = {
            'tool_name': tool_name,
            'args': list(args),
            'kwargs': kwargs,
            'use_cache': use_cache
        }
        
        return self._request('POST', '/tool/call', data=data)
    
    def list_tools(self) -> List[str]:
        """
        List available tools (Phase 4)
        
        Returns:
            List of tool names
        """
        result = self._request('GET', '/tools')
        return result.get('tools', [])
    
    def search_tools(self, query: str) -> List[str]:
        """
        Search for tools (Phase 4)
        
        Args:
            query: Search query
            
        Returns:
            List of matching tool names
        """
        result = self._request('GET', '/tools/search', params={'query': query})
        return result.get('tools', [])
    
    # ========================================================================
    # PHASE 1: KNOWLEDGE
    # ========================================================================
    
    def retrieve_knowledge(
        self,
        query: str,
        limit: int = 5,
        index_name: str = "knowledge"
    ) -> Dict[str, Any]:
        """
        Retrieve knowledge (Phase 1)
        
        Args:
            query: Knowledge query
            limit: Maximum results
            index_name: Index name
            
        Returns:
            Knowledge retrieval result
        """
        data = {
            'query': query,
            'limit': limit,
            'index_name': index_name
        }
        
        return self._request('POST', '/knowledge', data=data)
    
    # ========================================================================
    # PHASE 2: SEARCH
    # ========================================================================
    
    def hybrid_search(
        self,
        query: str,
        limit: int = 10,
        index_name: str = "documents"
    ) -> Dict[str, Any]:
        """
        Hybrid search (Phase 2)
        
        Args:
            query: Search query
            limit: Maximum results
            index_name: Index name
            
        Returns:
            Search results
        """
        data = {
            'query': query,
            'limit': limit,
            'index_name': index_name
        }
        
        return self._request('POST', '/search', data=data)
    
    # ========================================================================
    # PHASE 3: WEB INTELLIGENCE
    # ========================================================================
    
    def scrape_web(self, url: str) -> Dict[str, Any]:
        """
        Scrape web content (Phase 3)
        
        Args:
            url: URL to scrape
            
        Returns:
            Scraped content
        """
        data = {'url': url}
        return self._request('POST', '/web/scrape', data=data)
    
    def get_news(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get news (Phase 3)
        
        Args:
            query: News query
            category: News category
            limit: Maximum articles
            
        Returns:
            News articles
        """
        data = {
            'query': query,
            'category': category,
            'limit': limit
        }
        
        return self._request('POST', '/web/news', data=data)
    
    def search_web(
        self,
        query: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search web (Phase 3)
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            Web search results
        """
        data = {
            'query': query,
            'limit': limit
        }
        
        return self._request('POST', '/web/search', data=data)
    
    # ========================================================================
    # MONITORING & MANAGEMENT
    # ========================================================================
    
    def get_health(self) -> Dict[str, Any]:
        """
        Get health status
        
        Returns:
            Health status including all phases
        """
        return self._request('GET', '/health')
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics
        
        Returns:
            Performance stats including cache, monitoring
        """
        return self._request('GET', '/stats')
    
    def get_conversation_history(
        self,
        user_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get conversation history
        
        Args:
            user_id: User identifier
            limit: Maximum messages
            
        Returns:
            Conversation history
        """
        params = {'limit': limit} if limit else {}
        result = self._request('GET', f'/history/{user_id}', params=params)
        return result.get('history', [])
    
    def clear_conversation(self, user_id: str) -> bool:
        """
        Clear conversation history
        
        Args:
            user_id: User identifier
            
        Returns:
            Success status
        """
        result = self._request('DELETE', f'/history/{user_id}')
        return result.get('success', False)
    
    def __repr__(self):
        return f"<UnifiedBrainClient base_url={self.base_url}>"


# Convenience function
def create_client(base_url: str = "http://localhost:8000") -> UnifiedBrainClient:
    """
    Create a client instance
    
    Args:
        base_url: Base URL of the API server
        
    Returns:
        UnifiedBrainClient instance
    """
    return UnifiedBrainClient(base_url)


if __name__ == "__main__":
    # Demo usage
    print("Unified Brain API Client Demo")
    print("=" * 60)
    
    client = create_client()
    
    # Check health
    print("\n1. Health Check:")
    health = client.get_health()
    print(f"   Status: {health.get('status')}")
    
    # List tools
    print("\n2. List Tools:")
    tools = client.list_tools()
    print(f"   Available: {len(tools)} tools")
    print(f"   Sample: {', '.join(tools[:5])}")
    
    # Execute code
    print("\n3. Execute Code:")
    result = client.execute_code("print('Hello from API!')")
    if result.get('success'):
        print(f"   Output: {result['output']}")
    
    # Call tool
    print("\n4. Call Tool:")
    result = client.call_tool("add", 10, 20)
    if result.get('success'):
        print(f"   Result: 10 + 20 = {result['result']}")
    
    print("\n✅ Client demo complete!")
