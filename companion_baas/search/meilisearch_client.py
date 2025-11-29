"""
Meilisearch Client for Fast Full-Text Search
=============================================

Handles connection and operations with Meilisearch
for lightning-fast search (<50ms) with typo tolerance
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

try:
    import meilisearch
    from meilisearch.client import Client
    from meilisearch.index import Index
    MEILISEARCH_AVAILABLE = True
except ImportError:
    MEILISEARCH_AVAILABLE = False

# Try relative import first, fallback to absolute
try:
    from ..config import get_config
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import get_config

logger = logging.getLogger(__name__)


class MeilisearchClient:
    """Client for Meilisearch fast full-text search"""
    
    def __init__(self):
        """Initialize Meilisearch client"""
        if not MEILISEARCH_AVAILABLE:
            logger.warning("Meilisearch library not installed. Run: pip install meilisearch")
            self.client = None
            self.enabled = False
            return
        
        try:
            config = get_config()
            self.host = config.meilisearch.host
            self.port = config.meilisearch.port
            self.master_key = config.meilisearch.master_key
            self.enabled = config.meilisearch.enabled
            
            if not self.enabled:
                logger.info("Meilisearch is disabled in configuration")
                self.client = None
                return
            
            # Build URL
            url = f"http://{self.host}:{self.port}"
            
            # Initialize client
            self.client = Client(url, self.master_key)
            
            # Test connection
            health = self.client.health()
            logger.info(f"✅ Meilisearch connected successfully: {health['status']}")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Meilisearch: {e}")
            self.client = None
            self.enabled = False
    
    def create_index(self, index_name: str) -> bool:
        """
        Create a new search index
        
        Args:
            index_name: Name of the index
            
        Returns:
            Success status
        """
        if not self.enabled or not self.client:
            logger.warning("Meilisearch not available")
            return False
        
        try:
            # Create index
            task = self.client.create_index(index_name, {'primaryKey': 'id'})
            logger.info(f"✅ Created index: {index_name}")
            return True
            
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info(f"Index {index_name} already exists")
                return True
            logger.error(f"❌ Failed to create index {index_name}: {e}")
            return False
    
    def configure_index(
        self,
        index_name: str,
        searchable_attributes: Optional[List[str]] = None,
        filterable_attributes: Optional[List[str]] = None,
        sortable_attributes: Optional[List[str]] = None
    ) -> bool:
        """
        Configure index settings
        
        Args:
            index_name: Index name
            searchable_attributes: Fields to search in
            filterable_attributes: Fields to filter on
            sortable_attributes: Fields to sort by
            
        Returns:
            Success status
        """
        if not self.enabled or not self.client:
            return False
        
        try:
            index = self.client.index(index_name)
            
            # Configure searchable attributes
            if searchable_attributes:
                index.update_searchable_attributes(searchable_attributes)
                logger.info(f"✅ Configured searchable attributes for {index_name}")
            
            # Configure filterable attributes
            if filterable_attributes:
                index.update_filterable_attributes(filterable_attributes)
                logger.info(f"✅ Configured filterable attributes for {index_name}")
            
            # Configure sortable attributes
            if sortable_attributes:
                index.update_sortable_attributes(sortable_attributes)
                logger.info(f"✅ Configured sortable attributes for {index_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to configure index {index_name}: {e}")
            return False
    
    def add_documents(
        self,
        index_name: str,
        documents: List[Dict[str, Any]]
    ) -> bool:
        """
        Add documents to index
        
        Args:
            index_name: Index name
            documents: List of documents to add
            
        Returns:
            Success status
        """
        if not self.enabled or not self.client:
            return False
        
        try:
            index = self.client.index(index_name)
            
            # Add documents
            task = index.add_documents(documents)
            logger.info(f"✅ Added {len(documents)} documents to {index_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to add documents to {index_name}: {e}")
            return False
    
    def search(
        self,
        index_name: str,
        query: str,
        limit: int = 10,
        offset: int = 0,
        filters: Optional[str] = None,
        sort: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Search documents in index
        
        Args:
            index_name: Index name
            query: Search query
            limit: Number of results
            offset: Result offset for pagination
            filters: Filter expression
            sort: Sort criteria
            
        Returns:
            Search results with hits and metadata
        """
        if not self.enabled or not self.client:
            return {'hits': [], 'query': query, 'processingTimeMs': 0}
        
        try:
            index = self.client.index(index_name)
            
            # Build search parameters
            search_params = {
                'limit': limit,
                'offset': offset
            }
            
            if filters:
                search_params['filter'] = filters
            
            if sort:
                search_params['sort'] = sort
            
            # Perform search
            results = index.search(query, search_params)
            
            logger.info(
                f"🔍 Search completed: '{query}' in {results['processingTimeMs']}ms, "
                f"found {len(results['hits'])} results"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Search failed for '{query}' in {index_name}: {e}")
            return {'hits': [], 'query': query, 'processingTimeMs': 0, 'error': str(e)}
    
    def delete_document(self, index_name: str, document_id: str) -> bool:
        """Delete a document by ID"""
        if not self.enabled or not self.client:
            return False
        
        try:
            index = self.client.index(index_name)
            task = index.delete_document(document_id)
            logger.info(f"✅ Deleted document {document_id} from {index_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to delete document {document_id}: {e}")
            return False
    
    def delete_index(self, index_name: str) -> bool:
        """Delete an entire index"""
        if not self.enabled or not self.client:
            return False
        
        try:
            task = self.client.delete_index(index_name)
            logger.info(f"✅ Deleted index: {index_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to delete index {index_name}: {e}")
            return False
    
    def get_stats(self, index_name: str) -> Dict[str, Any]:
        """Get index statistics"""
        if not self.enabled or not self.client:
            return {}
        
        try:
            index = self.client.index(index_name)
            stats = index.get_stats()
            return stats
            
        except Exception as e:
            logger.error(f"❌ Failed to get stats for {index_name}: {e}")
            return {}


# Global instance
_meilisearch_client = None

def get_meilisearch_client() -> MeilisearchClient:
    """Get or create global Meilisearch client"""
    global _meilisearch_client
    if _meilisearch_client is None:
        _meilisearch_client = MeilisearchClient()
    return _meilisearch_client
