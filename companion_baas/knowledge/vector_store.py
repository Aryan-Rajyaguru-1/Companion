"""
Vector Store - Embedding Generation and Management
Handles text embeddings for semantic search
"""

import logging
from typing import List, Optional, Union
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

# Try relative import first, fallback to absolute
try:
    from ..config import get_config
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import get_config

logger = logging.getLogger(__name__)


class VectorStore:
    """Manages text embeddings for semantic search"""
    
    def __init__(self):
        """Initialize vector store with embedding model"""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning("sentence-transformers not installed. Run: pip install sentence-transformers")
            self.model = None
            self.enabled = False
            return
        
        config = get_config().elasticsearch
        
        if not config.enabled:
            logger.info("Vector store disabled (Elasticsearch disabled)")
            self.model = None
            self.enabled = False
            return
        
        try:
            # Load embedding model
            logger.info(f"Loading embedding model: {config.embedding_model}")
            self.model = SentenceTransformer(config.embedding_model)
            self.vector_dim = config.vector_dim
            self.enabled = True
            logger.info(f"✅ Vector store initialized (dim={self.vector_dim})")
            
        except Exception as e:
            logger.error(f"❌ Failed to load embedding model: {e}")
            self.model = None
            self.enabled = False
    
    def encode_text(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text
        
        Args:
            text: Text to encode
            
        Returns:
            List of floats representing the embedding, or None if disabled
        """
        if not self.enabled or not text:
            return None
        
        try:
            # Generate embedding
            embedding = self.model.encode(text, convert_to_numpy=True)
            
            # Convert to list
            embedding_list = embedding.tolist()
            
            return embedding_list
            
        except Exception as e:
            logger.error(f"❌ Failed to encode text: {e}")
            return None
    
    def encode(self, text: str) -> Optional[List[float]]:
        """
        Alias for encode_text for convenience
        
        Args:
            text: Text to encode
            
        Returns:
            List of floats representing the embedding, or None if disabled
        """
        return self.encode_text(text)
    
    def encode_texts(self, texts: List[str]) -> Optional[List[List[float]]]:
        """
        Generate embeddings for multiple texts (batched for efficiency)
        
        Args:
            texts: List of texts to encode
            
        Returns:
            List of embeddings, or None if disabled
        """
        if not self.enabled or not texts:
            return None
        
        try:
            # Batch encode for efficiency
            embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
            
            # Convert to list of lists
            embeddings_list = [emb.tolist() for emb in embeddings]
            
            return embeddings_list
            
        except Exception as e:
            logger.error(f"❌ Failed to encode texts: {e}")
            return None
    
    def compute_similarity(self, 
                          embedding1: List[float], 
                          embedding2: List[float]) -> float:
        """
        Compute cosine similarity between two embeddings
        
        Args:
            embedding1: First embedding
            embedding2: Second embedding
            
        Returns:
            Similarity score (0-1)
        """
        if not self.enabled:
            return 0.0
        
        try:
            # Convert to numpy arrays
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            # Compute cosine similarity
            similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
            
            # Normalize to 0-1 range
            similarity = (similarity + 1) / 2
            
            return float(similarity)
            
        except Exception as e:
            logger.error(f"❌ Failed to compute similarity: {e}")
            return 0.0
    
    def find_most_similar(self,
                         query_embedding: List[float],
                         candidate_embeddings: List[List[float]],
                         top_k: int = 5) -> List[tuple]:
        """
        Find most similar embeddings from candidates
        
        Args:
            query_embedding: Query embedding
            candidate_embeddings: List of candidate embeddings
            top_k: Number of top results to return
            
        Returns:
            List of (index, similarity_score) tuples
        """
        if not self.enabled or not candidate_embeddings:
            return []
        
        try:
            # Compute similarities
            similarities = []
            for idx, candidate in enumerate(candidate_embeddings):
                sim = self.compute_similarity(query_embedding, candidate)
                similarities.append((idx, sim))
            
            # Sort by similarity (descending)
            similarities.sort(key=lambda x: x[1], reverse=True)
            
            # Return top_k
            return similarities[:top_k]
            
        except Exception as e:
            logger.error(f"❌ Failed to find similar: {e}")
            return []
    
    def get_embedding_dim(self) -> int:
        """Get the dimensionality of embeddings"""
        return self.vector_dim if self.enabled else 0
    
    def is_enabled(self) -> bool:
        """Check if vector store is enabled"""
        return self.enabled


# Singleton instance
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get global vector store instance"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


# Convenience functions
def encode_text(text: str) -> Optional[List[float]]:
    """Quick function to encode text"""
    return get_vector_store().encode_text(text)


def encode_texts(texts: List[str]) -> Optional[List[List[float]]]:
    """Quick function to encode multiple texts"""
    return get_vector_store().encode_texts(texts)


def compute_similarity(embedding1: List[float], embedding2: List[float]) -> float:
    """Quick function to compute similarity"""
    return get_vector_store().compute_similarity(embedding1, embedding2)
