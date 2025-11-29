"""
Unified Search Engine
====================

Combines Meilisearch (fast text search) with Elasticsearch (vector search)
for powerful hybrid search capabilities
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

from .meilisearch_client import get_meilisearch_client

# Try to import Elasticsearch components
try:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from knowledge.elasticsearch_client import get_elasticsearch_client
    from knowledge.vector_store import get_vector_store
    KNOWLEDGE_AVAILABLE = True
except ImportError:
    KNOWLEDGE_AVAILABLE = False

logger = logging.getLogger(__name__)


class SearchEngine:
    """
    Unified search engine combining multiple search backends
    
    Capabilities:
    - Fast text search (Meilisearch) - <50ms
    - Semantic vector search (Elasticsearch) - similarity based
    - Hybrid search - combines both for best results
    """
    
    def __init__(self):
        """Initialize search engine with all available backends"""
        self.meilisearch = get_meilisearch_client()
        
        if KNOWLEDGE_AVAILABLE:
            self.elasticsearch = get_elasticsearch_client()
            self.vector_store = get_vector_store()
        else:
            self.elasticsearch = None
            self.vector_store = None
        
        # Check which backends are available
        self.text_search_enabled = self.meilisearch.enabled
        self.vector_search_enabled = (
            KNOWLEDGE_AVAILABLE and 
            self.elasticsearch.enabled and 
            self.vector_store.enabled
        )
        
        logger.info(
            f"🔍 Search Engine initialized: "
            f"Text={self.text_search_enabled}, "
            f"Vector={self.vector_search_enabled}"
        )
    
    def fast_search(
        self,
        query: str,
        index_name: str = "conversations",
        limit: int = 10,
        filters: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fast text search using Meilisearch (<50ms)
        
        Args:
            query: Search query
            index_name: Index to search in
            limit: Number of results
            filters: Filter expression
            
        Returns:
            Search results
        """
        if not self.text_search_enabled:
            logger.warning("Text search not available")
            return {'hits': [], 'query': query}
        
        try:
            results = self.meilisearch.search(
                index_name=index_name,
                query=query,
                limit=limit,
                filters=filters
            )
            
            return {
                'success': True,
                'hits': results['hits'],
                'query': query,
                'processing_time_ms': results.get('processingTimeMs', 0),
                'estimated_total_hits': results.get('estimatedTotalHits', 0)
            }
            
        except Exception as e:
            logger.error(f"❌ Fast search failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'hits': []
            }
    
    def semantic_search(
        self,
        query: str,
        index_name: str = None,
        limit: int = 10,
        min_score: float = 0.5
    ) -> Dict[str, Any]:
        """
        Semantic vector search using Elasticsearch
        
        Args:
            query: Search query
            index_name: Index to search (optional)
            limit: Number of results
            min_score: Minimum similarity score (0-1)
            
        Returns:
            Search results with similarity scores
        """
        if not self.vector_search_enabled:
            logger.warning("Vector search not available")
            return {'hits': [], 'query': query}
        
        try:
            # Generate query embedding
            query_embedding = self.vector_store.encode_text(query)
            
            # Search similar documents
            results = self.elasticsearch.search_similar(
                index_name=index_name,
                query_embedding=query_embedding,
                k=limit
            )
            
            return {
                'success': True,
                'hits': results,
                'query': query,
                'search_type': 'semantic'
            }
            
        except Exception as e:
            logger.error(f"❌ Semantic search failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'hits': []
            }
    
    def hybrid_search(
        self,
        query: str,
        index_name: str = "conversations",
        limit: int = 10,
        text_weight: float = 0.5,
        vector_weight: float = 0.5
    ) -> Dict[str, Any]:
        """
        Hybrid search combining text and vector search
        
        Args:
            query: Search query
            limit: Number of results
            text_weight: Weight for text search results (0-1)
            vector_weight: Weight for vector search results (0-1)
            index_name: Meilisearch index name
            
        Returns:
            Combined search results
        """
        if not self.text_search_enabled and not self.vector_search_enabled:
            logger.warning("No search backend available")
            return {'hits': [], 'query': query}
        
        try:
            results = []
            
            # Get text search results
            if self.text_search_enabled:
                text_results = self.fast_search(query, index_name=index_name, limit=limit*2)
                for hit in text_results.get('hits', []):
                    results.append({
                        **hit,
                        '_score': text_weight,
                        '_source': 'text_search'
                    })
            
            # Get vector search results
            if self.vector_search_enabled:
                vector_results = self.semantic_search(query, index_name=index_name, limit=limit*2)
                for hit in vector_results.get('hits', []):
                    # Check if document already in results
                    existing = next((r for r in results if r.get('id') == hit.get('id')), None)
                    if existing:
                        # Boost score
                        existing['_score'] += vector_weight * hit.get('score', 0.5)
                        existing['_source'] = 'hybrid'
                    else:
                        results.append({
                            **hit,
                            '_score': vector_weight * hit.get('score', 0.5),
                            '_source': 'vector_search'
                        })
            
            # Sort by score and limit
            results.sort(key=lambda x: x.get('_score', 0), reverse=True)
            results = results[:limit]
            
            return {
                'success': True,
                'hits': results,
                'query': query,
                'search_type': 'hybrid',
                'text_enabled': self.text_search_enabled,
                'vector_enabled': self.vector_search_enabled
            }
            
        except Exception as e:
            logger.error(f"❌ Hybrid search failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'hits': []
            }
    
    def index_document(
        self,
        document: Dict[str, Any],
        index_name: str = "conversations",
        generate_embedding: bool = True
    ) -> bool:
        """
        Index a document in both search backends
        
        Args:
            document: Document to index
            index_name: Index name
            generate_embedding: Whether to generate vector embedding
            
        Returns:
            Success status
        """
        success = True
        
        # Index in Meilisearch
        if self.text_search_enabled:
            try:
                self.meilisearch.add_documents(index_name, [document])
                logger.info(f"✅ Indexed document in Meilisearch")
            except Exception as e:
                logger.error(f"❌ Failed to index in Meilisearch: {e}")
                success = False
        
        # Index in Elasticsearch with embedding
        if self.vector_search_enabled and generate_embedding:
            try:
                # Generate embedding from content
                content = document.get('content', document.get('text', ''))
                if content:
                    embedding = self.vector_store.encode_text(content)
                    self.elasticsearch.index_document(document, embedding)
                    logger.info(f"✅ Indexed document in Elasticsearch")
            except Exception as e:
                logger.error(f"❌ Failed to index in Elasticsearch: {e}")
                success = False
        
        return success
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all search backends"""
        stats = {
            'text_search': {
                'enabled': self.text_search_enabled,
                'backend': 'meilisearch'
            },
            'vector_search': {
                'enabled': self.vector_search_enabled,
                'backend': 'elasticsearch'
            }
        }
        
        # Get Meilisearch stats
        if self.text_search_enabled:
            try:
                ms_stats = self.meilisearch.get_stats("conversations")
                stats['text_search']['stats'] = ms_stats
            except:
                pass
        
        # Get Elasticsearch stats
        if self.vector_search_enabled:
            try:
                es_stats = self.elasticsearch.get_stats()
                stats['vector_search']['stats'] = es_stats
            except:
                pass
        
        return stats


# Global instance
_search_engine = None

def get_search_engine() -> SearchEngine:
    """Get or create global search engine"""
    global _search_engine
    if _search_engine is None:
        _search_engine = SearchEngine()
    return _search_engine
