"""
Knowledge Layer - RAG Implementation
Provides semantic search and context retrieval for enhanced AI responses
"""

from .elasticsearch_client import ElasticsearchClient, get_elasticsearch_client
from .vector_store import VectorStore, get_vector_store, encode_text, encode_texts, compute_similarity
from .retriever import KnowledgeRetriever, get_knowledge_retriever

__all__ = [
    'ElasticsearchClient',
    'get_elasticsearch_client',
    'VectorStore',
    'get_vector_store',
    'encode_text',
    'encode_texts',
    'compute_similarity',
    'KnowledgeRetriever',
    'get_knowledge_retriever'
]
