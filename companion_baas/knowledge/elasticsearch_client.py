"""
Elasticsearch Client for Vector Search
Handles connection and operations with Elasticsearch
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

try:
    from elasticsearch import Elasticsearch, helpers
    from elasticsearch.exceptions import ConnectionError, NotFoundError
    ELASTICSEARCH_AVAILABLE = True
except ImportError:
    ELASTICSEARCH_AVAILABLE = False

# Try relative import first, fallback to absolute
try:
    from ..config import get_config
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import get_config

logger = logging.getLogger(__name__)


class ElasticsearchClient:
    """Client for Elasticsearch operations"""
    
    def __init__(self):
        """Initialize Elasticsearch client"""
        if not ELASTICSEARCH_AVAILABLE:
            logger.warning("Elasticsearch library not installed. Run: pip install elasticsearch")
            self.client = None
            self.enabled = False
            return
        
        config = get_config().elasticsearch
        
        if not config.enabled:
            logger.info("Elasticsearch is disabled in configuration")
            self.client = None
            self.enabled = False
            return
        
        try:
            self.client = Elasticsearch(
                [f"http://{config.host}:{config.port}"],
                request_timeout=30,
                max_retries=3,
                retry_on_timeout=True
            )
            
            # Test connection
            if self.client.ping():
                logger.info(f"✅ Connected to Elasticsearch at {config.host}:{config.port}")
                self.enabled = True
                self._ensure_index_exists()
            else:
                logger.error("❌ Failed to ping Elasticsearch")
                self.client = None
                self.enabled = False
                
        except Exception as e:
            logger.error(f"❌ Elasticsearch connection error: {e}")
            self.client = None
            self.enabled = False
    
    def _ensure_index_exists(self):
        """Create index if it doesn't exist"""
        if not self.enabled:
            return
        
        config = get_config().elasticsearch
        index_name = config.index_name
        
        try:
            if not self.client.indices.exists(index=index_name):
                # Create index with vector mapping
                mapping = {
                    "mappings": {
                        "properties": {
                            "message": {"type": "text"},
                            "response": {"type": "text"},
                            "embedding": {
                                "type": "dense_vector",
                                "dims": config.vector_dim,
                                "index": True,
                                "similarity": "cosine"
                            },
                            "user_id": {"type": "keyword"},
                            "conversation_id": {"type": "keyword"},
                            "app_type": {"type": "keyword"},
                            "timestamp": {"type": "date"},
                            "metadata": {"type": "object", "enabled": False}
                        }
                    }
                }
                
                self.client.indices.create(index=index_name, body=mapping)
                logger.info(f"✅ Created Elasticsearch index: {index_name}")
        except Exception as e:
            logger.error(f"❌ Failed to create index: {e}")
    
    def create_index(self, index_name: str, dimension: int = 384) -> bool:
        """
        Create a new index with vector mapping
        
        Args:
            index_name: Name of the index to create
            dimension: Vector dimension for embeddings
            
        Returns:
            bool: Success status
        """
        if not self.enabled:
            logger.warning("Elasticsearch not enabled")
            return False
        
        try:
            if self.client.indices.exists(index=index_name):
                logger.info(f"Index {index_name} already exists")
                return True
            
            mapping = {
                "mappings": {
                    "properties": {
                        "text": {"type": "text"},
                        "title": {"type": "text"},
                        "content": {"type": "text"},
                        "summary": {"type": "text"},
                        "embedding": {
                            "type": "dense_vector",
                            "dims": dimension,
                            "index": True,
                            "similarity": "cosine"
                        },
                        "category": {"type": "keyword"},
                        "tags": {"type": "keyword"},
                        "timestamp": {"type": "date"},
                        "metadata": {"type": "object", "enabled": False}
                    }
                }
            }
            
            self.client.indices.create(index=index_name, body=mapping)
            logger.info(f"✅ Created Elasticsearch index: {index_name} (dim={dimension})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create index {index_name}: {e}")
            return False
    
    def index_document(self, 
                      message: str,
                      response: str,
                      embedding: List[float],
                      user_id: Optional[str] = None,
                      conversation_id: Optional[str] = None,
                      app_type: Optional[str] = None,
                      metadata: Optional[Dict] = None) -> bool:
        """
        Index a document with its embedding
        
        Args:
            message: User message
            response: AI response
            embedding: Vector embedding of the message
            user_id: User identifier
            conversation_id: Conversation identifier
            app_type: Type of application
            metadata: Additional metadata
            
        Returns:
            bool: Success status
        """
        if not self.enabled:
            return False
        
        try:
            config = get_config().elasticsearch
            
            document = {
                "message": message,
                "response": response,
                "embedding": embedding,
                "user_id": user_id,
                "conversation_id": conversation_id,
                "app_type": app_type,
                "timestamp": datetime.utcnow(),
                "metadata": metadata or {}
            }
            
            result = self.client.index(
                index=config.index_name,
                document=document
            )
            
            logger.debug(f"✅ Indexed document: {result['_id']}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to index document: {e}")
            return False
    
    def index_doc(self, index_name: str, doc_id: str, document: Dict[str, Any]) -> bool:
        """
        Index a document in a specific index (flexible version)
        
        Args:
            index_name: Name of the index
            doc_id: Document ID
            document: Document to index (should include 'embedding' field)
            
        Returns:
            bool: Success status
        """
        if not self.enabled:
            return False
        
        try:
            # Add timestamp if not present
            if 'timestamp' not in document:
                document['timestamp'] = datetime.utcnow()
            
            result = self.client.index(
                index=index_name,
                id=doc_id,
                document=document
            )
            
            logger.debug(f"✅ Indexed document {doc_id} in {index_name}: {result['result']}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to index document {doc_id} in {index_name}: {e}")
            return False
    
    def search_similar(self,
                      index_name: Optional[str] = None,
                      query_embedding: List[float] = None,
                      top_k: int = 5,
                      k: int = 5,
                      user_id: Optional[str] = None,
                      app_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for similar documents using vector similarity
        
        Args:
            index_name: Name of the index (defaults to config index)
            query_embedding: Vector embedding of the query
            top_k: Number of results to return (deprecated, use k)
            k: Number of results to return
            user_id: Filter by user ID
            app_type: Filter by app type
            
        Returns:
            List of similar documents with scores
        """
        if not self.enabled:
            return []
        
        # Use k if provided, otherwise fall back to top_k
        num_results = k if k != 5 else top_k
        
        try:
            config = get_config().elasticsearch
            idx = index_name or config.index_name
            
            # Handle case where query_embedding wasn't provided
            if query_embedding is None:
                logger.warning("No query_embedding provided to search_similar")
                return []
            
            # Convert numpy array to list if needed
            if hasattr(query_embedding, 'tolist'):
                query_embedding = query_embedding.tolist()
            
            # Build query
            query = {
                "knn": {
                    "field": "embedding",
                    "query_vector": query_embedding,
                    "k": num_results,
                    "num_candidates": num_results * 2
                }
            }
            
            # Add filters if provided
            if user_id or app_type:
                must_filters = []
                if user_id:
                    must_filters.append({"term": {"user_id": user_id}})
                if app_type:
                    must_filters.append({"term": {"app_type": app_type}})
                
                query = {
                    "query": {
                        "bool": {
                            "must": [{"knn": query["knn"]}],
                            "filter": must_filters
                        }
                    }
                }
            
            # Execute search (add size to body for ES 8.x)
            if 'query' not in query:
                # Simple knn query
                search_body = {
                    **query,
                    "size": num_results
                }
            else:
                # Complex query with filters
                search_body = {
                    **query,
                    "size": num_results
                }
            
            response = self.client.search(
                index=idx,
                body=search_body
            )
            
            # Parse results
            results = []
            for hit in response['hits']['hits']:
                source = hit['_source']
                # Handle different document structures
                if 'message' in source:
                    results.append({
                        'message': source['message'],
                        'response': source['response'],
                        'score': hit['_score'],
                        'user_id': source.get('user_id'),
                        'conversation_id': source.get('conversation_id'),
                        'app_type': source.get('app_type'),
                        'timestamp': source.get('timestamp'),
                        'metadata': source.get('metadata', {})
                    })
                else:
                    # Generic document structure
                    results.append({
                        '_id': hit['_id'],
                        '_score': hit['_score'],
                        '_source': source
                    })
            
            logger.debug(f"✅ Found {len(results)} similar documents")
            return results
            
        except Exception as e:
            logger.error(f"❌ Search failed: {e}")
            return []
    
    def text_search(self,
                   query: str,
                   top_k: int = 5,
                   user_id: Optional[str] = None,
                   app_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Full-text search across messages and responses
        
        Args:
            query: Search query text
            top_k: Number of results to return
            user_id: Filter by user ID
            app_type: Filter by app type
            
        Returns:
            List of matching documents
        """
        if not self.enabled:
            return []
        
        try:
            config = get_config().elasticsearch
            
            # Build query
            must_clauses = [
                {
                    "multi_match": {
                        "query": query,
                        "fields": ["message^2", "response"],
                        "type": "best_fields",
                        "fuzziness": "AUTO"
                    }
                }
            ]
            
            # Add filters
            filter_clauses = []
            if user_id:
                filter_clauses.append({"term": {"user_id": user_id}})
            if app_type:
                filter_clauses.append({"term": {"app_type": app_type}})
            
            query_body = {
                "query": {
                    "bool": {
                        "must": must_clauses,
                        "filter": filter_clauses
                    }
                },
                "sort": [
                    {"_score": {"order": "desc"}},
                    {"timestamp": {"order": "desc"}}
                ]
            }
            
            # Execute search
            response = self.client.search(
                index=config.index_name,
                body=query_body,
                size=top_k
            )
            
            # Parse results
            results = []
            for hit in response['hits']['hits']:
                source = hit['_source']
                results.append({
                    'message': source['message'],
                    'response': source['response'],
                    'score': hit['_score'],
                    'user_id': source.get('user_id'),
                    'conversation_id': source.get('conversation_id'),
                    'app_type': source.get('app_type'),
                    'timestamp': source.get('timestamp'),
                    'metadata': source.get('metadata', {})
                })
            
            logger.debug(f"✅ Text search returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"❌ Text search failed: {e}")
            return []
    
    def get_conversation_history(self,
                                conversation_id: str,
                                limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get full conversation history
        
        Args:
            conversation_id: Conversation identifier
            limit: Maximum number of messages
            
        Returns:
            List of conversation messages
        """
        if not self.enabled:
            return []
        
        try:
            config = get_config().elasticsearch
            
            query = {
                "query": {
                    "term": {"conversation_id": conversation_id}
                },
                "sort": [{"timestamp": {"order": "asc"}}],
                "size": limit
            }
            
            response = self.client.search(
                index=config.index_name,
                body=query
            )
            
            results = []
            for hit in response['hits']['hits']:
                source = hit['_source']
                results.append({
                    'message': source['message'],
                    'response': source['response'],
                    'timestamp': source.get('timestamp')
                })
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to get conversation history: {e}")
            return []
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete all messages in a conversation"""
        if not self.enabled:
            return False
        
        try:
            config = get_config().elasticsearch
            
            query = {
                "query": {
                    "term": {"conversation_id": conversation_id}
                }
            }
            
            self.client.delete_by_query(
                index=config.index_name,
                body=query
            )
            
            logger.info(f"✅ Deleted conversation: {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to delete conversation: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get Elasticsearch statistics"""
        if not self.enabled:
            return {'enabled': False}
        
        try:
            config = get_config().elasticsearch
            
            count = self.client.count(index=config.index_name)
            
            return {
                'enabled': True,
                'total_documents': count['count'],
                'index_name': config.index_name,
                'host': f"{config.host}:{config.port}"
            }
        except Exception as e:
            logger.error(f"❌ Failed to get stats: {e}")
            return {'enabled': True, 'error': str(e)}


# Singleton instance
_client: Optional[ElasticsearchClient] = None


def get_elasticsearch_client() -> ElasticsearchClient:
    """Get global Elasticsearch client instance"""
    global _client
    if _client is None:
        _client = ElasticsearchClient()
    return _client
