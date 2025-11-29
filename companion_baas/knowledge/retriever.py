"""
Knowledge Retriever - RAG (Retrieval-Augmented Generation)
Combines vector search with LLM for enhanced responses
"""

import logging
from typing import List, Dict, Optional, Any

from .elasticsearch_client import get_elasticsearch_client
from .vector_store import get_vector_store

logger = logging.getLogger(__name__)


class KnowledgeRetriever:
    """
    RAG implementation for Companion Brain
    Retrieves relevant context from knowledge base for enhanced responses
    """
    
    def __init__(self):
        """Initialize knowledge retriever"""
        self.es_client = get_elasticsearch_client()
        self.vector_store = get_vector_store()
        self.enabled = self.es_client.enabled and self.vector_store.enabled
        
        if self.enabled:
            logger.info("✅ Knowledge Retriever initialized")
        else:
            logger.warning("⚠️  Knowledge Retriever disabled (dependencies not available)")
    
    def index_conversation(self,
                          message: str,
                          response: str,
                          user_id: Optional[str] = None,
                          conversation_id: Optional[str] = None,
                          app_type: Optional[str] = None,
                          metadata: Optional[Dict] = None) -> bool:
        """
        Index a conversation turn in the knowledge base
        
        Args:
            message: User message
            response: AI response
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
            # Generate embedding for the message
            embedding = self.vector_store.encode_text(message)
            
            if embedding is None:
                logger.error("Failed to generate embedding")
                return False
            
            # Index in Elasticsearch
            success = self.es_client.index_document(
                message=message,
                response=response,
                embedding=embedding,
                user_id=user_id,
                conversation_id=conversation_id,
                app_type=app_type,
                metadata=metadata
            )
            
            if success:
                logger.debug(f"✅ Indexed conversation: {message[:50]}...")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Failed to index conversation: {e}")
            return False
    
    def search(self,
              query: str,
              top_k: int = 5,
              user_id: Optional[str] = None,
              app_type: Optional[str] = None,
              search_type: str = 'hybrid') -> List[Dict[str, Any]]:
        """
        Search the knowledge base for relevant context
        
        Args:
            query: Search query
            top_k: Number of results to return
            user_id: Filter by user ID
            app_type: Filter by app type
            search_type: 'vector', 'text', or 'hybrid'
            
        Returns:
            List of relevant documents with scores
        """
        if not self.enabled:
            return []
        
        try:
            if search_type == 'vector':
                return self._vector_search(query, top_k, user_id, app_type)
            elif search_type == 'text':
                return self._text_search(query, top_k, user_id, app_type)
            else:  # hybrid
                return self._hybrid_search(query, top_k, user_id, app_type)
                
        except Exception as e:
            logger.error(f"❌ Search failed: {e}")
            return []
    
    def _vector_search(self,
                      query: str,
                      top_k: int,
                      user_id: Optional[str],
                      app_type: Optional[str]) -> List[Dict[str, Any]]:
        """Perform vector similarity search"""
        # Generate query embedding
        query_embedding = self.vector_store.encode_text(query)
        
        if query_embedding is None:
            return []
        
        # Search Elasticsearch
        results = self.es_client.search_similar(
            query_embedding=query_embedding,
            top_k=top_k,
            user_id=user_id,
            app_type=app_type
        )
        
        return results
    
    def _text_search(self,
                    query: str,
                    top_k: int,
                    user_id: Optional[str],
                    app_type: Optional[str]) -> List[Dict[str, Any]]:
        """Perform full-text search"""
        results = self.es_client.text_search(
            query=query,
            top_k=top_k,
            user_id=user_id,
            app_type=app_type
        )
        
        return results
    
    def _hybrid_search(self,
                      query: str,
                      top_k: int,
                      user_id: Optional[str],
                      app_type: Optional[str]) -> List[Dict[str, Any]]:
        """
        Combine vector and text search for best results
        Uses RRF (Reciprocal Rank Fusion) to merge results
        """
        # Get results from both methods
        vector_results = self._vector_search(query, top_k * 2, user_id, app_type)
        text_results = self._text_search(query, top_k * 2, user_id, app_type)
        
        # Merge using RRF
        merged = self._merge_results(vector_results, text_results)
        
        # Return top_k
        return merged[:top_k]
    
    def _merge_results(self,
                      vector_results: List[Dict],
                      text_results: List[Dict]) -> List[Dict]:
        """
        Merge results using Reciprocal Rank Fusion (RRF)
        
        RRF score = sum(1 / (k + rank)) for each result list
        k = 60 is a common default
        """
        k = 60
        scores = {}
        documents = {}
        
        # Score vector results
        for rank, doc in enumerate(vector_results, 1):
            doc_id = doc['message']  # Use message as unique ID
            scores[doc_id] = scores.get(doc_id, 0) + (1 / (k + rank))
            documents[doc_id] = doc
        
        # Score text results
        for rank, doc in enumerate(text_results, 1):
            doc_id = doc['message']
            scores[doc_id] = scores.get(doc_id, 0) + (1 / (k + rank))
            documents[doc_id] = doc
        
        # Sort by RRF score
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Return documents with RRF scores
        results = []
        for doc_id, score in sorted_docs:
            doc = documents[doc_id].copy()
            doc['rrf_score'] = score
            results.append(doc)
        
        return results
    
    def get_context_for_query(self,
                             query: str,
                             max_context_length: int = 2000,
                             user_id: Optional[str] = None,
                             app_type: Optional[str] = None) -> str:
        """
        Get formatted context string for RAG
        
        Args:
            query: User query
            max_context_length: Maximum characters for context
            user_id: Filter by user
            app_type: Filter by app type
            
        Returns:
            Formatted context string
        """
        if not self.enabled:
            return ""
        
        try:
            # Search for relevant context
            results = self.search(
                query=query,
                top_k=5,
                user_id=user_id,
                app_type=app_type,
                search_type='hybrid'
            )
            
            if not results:
                return ""
            
            # Format context
            context_parts = []
            current_length = 0
            
            for idx, doc in enumerate(results, 1):
                # Format: "Context {idx}: Q: {message}\nA: {response}\n"
                part = f"Context {idx}:\nQ: {doc['message']}\nA: {doc['response']}\n"
                
                if current_length + len(part) > max_context_length:
                    break
                
                context_parts.append(part)
                current_length += len(part)
            
            if not context_parts:
                return ""
            
            context = "=== Relevant Context from Knowledge Base ===\n\n"
            context += "\n".join(context_parts)
            context += "\n=== End of Context ===\n"
            
            return context
            
        except Exception as e:
            logger.error(f"❌ Failed to get context: {e}")
            return ""
    
    def get_conversation_history(self,
                                conversation_id: str,
                                limit: int = 50) -> List[Dict[str, Any]]:
        """Get full conversation history"""
        if not self.enabled:
            return []
        
        return self.es_client.get_conversation_history(conversation_id, limit)
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation from knowledge base"""
        if not self.enabled:
            return False
        
        return self.es_client.delete_conversation(conversation_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics"""
        if not self.enabled:
            return {
                'enabled': False,
                'reason': 'Dependencies not available'
            }
        
        es_stats = self.es_client.get_stats()
        
        return {
            'enabled': True,
            'total_conversations': es_stats.get('total_documents', 0),
            'embedding_dim': self.vector_store.get_embedding_dim(),
            'index_name': es_stats.get('index_name', 'N/A'),
            'elasticsearch_host': es_stats.get('host', 'N/A')
        }
    
    def is_enabled(self) -> bool:
        """Check if knowledge retriever is enabled"""
        return self.enabled


# Singleton instance
_retriever: Optional[KnowledgeRetriever] = None


def get_knowledge_retriever() -> KnowledgeRetriever:
    """Get global knowledge retriever instance"""
    global _retriever
    if _retriever is None:
        _retriever = KnowledgeRetriever()
    return _retriever
