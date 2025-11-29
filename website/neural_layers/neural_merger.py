"""
Simple Neural Merger
TF-IDF based merging without heavy models
Uses scikit-learn for lightweight processing
"""

import logging
from typing import List, Dict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

logger = logging.getLogger(__name__)

class SimpleMerger:
    """Lightweight result merger using TF-IDF"""
    
    def __init__(self):
        # Lightweight TF-IDF with limited features
        self.vectorizer = TfidfVectorizer(
            max_features=100,  # Limit feature space
            stop_words='english',
            ngram_range=(1, 2)  # Unigrams and bigrams
        )
        logger.info("🔀 Merger initialized (TF-IDF)")
    
    def synthesize(self, results: List[Dict], max_length: int = 500) -> str:
        """
        Merge multiple results intelligently
        
        Args:
            results: List of result dicts from processor
            max_length: Maximum response length
            
        Returns:
            Merged response string
        """
        if not results:
            return "No results available."
        
        # Single result - no merging needed
        if len(results) == 1:
            return results[0].get('result', '')
        
        # Extract texts and metadata
        texts = []
        weights = []
        
        for r in results:
            text = r.get('result', '').strip()
            if not text or len(text) < 10:
                continue
            
            texts.append(text)
            
            # Calculate weight based on source
            weight = self._calculate_weight(r)
            weights.append(weight)
        
        if not texts:
            return "Unable to process results."
        
        if len(texts) == 1:
            return texts[0]
        
        try:
            # Merge using TF-IDF similarity
            merged = self._tfidf_merge(texts, weights, max_length)
            logger.info(f"✅ Merged {len(texts)} results into {len(merged)} chars")
            return merged
            
        except Exception as e:
            logger.error(f"Merge error: {e}, falling back to simple concat")
            # Fallback: weighted concatenation
            return self._simple_merge(texts, weights, max_length)
    
    def _calculate_weight(self, result: Dict) -> float:
        """Calculate importance weight for a result"""
        source = result.get('source', 'unknown')
        
        # Weight by source reliability
        source_weights = {
            'web': 1.3,      # Prefer fresh web data
            'cache': 1.1,    # Cached is pre-validated
            'llm': 1.0,      # Standard LLM response
            'timeout': 0.5,  # Lower priority
            'error': 0.1     # Lowest priority
        }
        
        return source_weights.get(source, 1.0)
    
    def _tfidf_merge(self, texts: List[str], weights: List[float], 
                     max_length: int) -> str:
        """Merge using TF-IDF similarity analysis"""
        try:
            # Compute TF-IDF matrix
            tfidf_matrix = self.vectorizer.fit_transform(texts)
            
            # Sort texts by weight
            weighted_texts = sorted(
                zip(texts, weights), 
                key=lambda x: x[1], 
                reverse=True
            )
            
            # Build merged response
            merged = self._deduplicate_merge(
                [t[0] for t in weighted_texts],
                max_length
            )
            
            return merged
            
        except Exception as e:
            logger.warning(f"TF-IDF merge failed: {e}")
            raise
    
    def _deduplicate_merge(self, texts: List[str], max_length: int) -> str:
        """
        Merge texts while removing duplicate sentences
        
        Args:
            texts: List of text strings
            max_length: Maximum output length
            
        Returns:
            Merged, deduplicated text
        """
        seen_sentences = set()
        result_sentences = []
        current_length = 0
        
        for text in texts:
            # Split into sentences
            sentences = self._split_sentences(text)
            
            for sent in sentences:
                sent_clean = sent.strip().lower()
                
                # Skip if duplicate or too short
                if not sent_clean or len(sent_clean) < 15:
                    continue
                
                # Check similarity with existing sentences
                if self._is_duplicate(sent_clean, seen_sentences):
                    continue
                
                # Add sentence
                seen_sentences.add(sent_clean)
                result_sentences.append(sent.strip())
                current_length += len(sent)
                
                # Stop if max length reached
                if current_length >= max_length:
                    break
            
            if current_length >= max_length:
                break
        
        # Join sentences properly
        merged = '. '.join(result_sentences)
        if merged and not merged.endswith('.'):
            merged += '.'
        
        return merged
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Simple sentence splitting
        sentences = text.replace('! ', '.|').replace('? ', '.|').split('.')
        return [s.strip() for s in sentences if s.strip()]
    
    def _is_duplicate(self, sentence: str, seen: set) -> bool:
        """Check if sentence is too similar to seen sentences"""
        # Simple word-based similarity
        words = set(sentence.split())
        
        for seen_sent in seen:
            seen_words = set(seen_sent.split())
            
            # Calculate Jaccard similarity
            if not words or not seen_words:
                continue
            
            intersection = len(words & seen_words)
            union = len(words | seen_words)
            similarity = intersection / union if union > 0 else 0
            
            # 70% similarity threshold
            if similarity > 0.7:
                return True
        
        return False
    
    def _simple_merge(self, texts: List[str], weights: List[float], 
                      max_length: int) -> str:
        """Simple fallback merge by concatenation"""
        # Sort by weight
        weighted = sorted(zip(texts, weights), key=lambda x: x[1], reverse=True)
        
        result = []
        current_length = 0
        
        for text, _ in weighted:
            if current_length + len(text) > max_length:
                break
            result.append(text)
            current_length += len(text)
        
        return ' '.join(result)
