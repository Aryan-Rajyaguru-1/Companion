"""
Ultra-Lightweight Query Decomposer
Breaks complex queries into manageable components
Optimized for low-resource systems (< 50MB RAM)
"""

import re
import logging

logger = logging.getLogger(__name__)

class UltraLightDecomposer:
    """Minimal resource query decomposition using pattern matching"""
    
    def __init__(self):
        # Temporal indicators for time-sensitive queries
        self.temporal_patterns = [
            'current', 'latest', 'now', '2025', '2024', 'today', 
            'recent', 'this year', 'new', 'updated'
        ]
        
        # Question types
        self.question_words = [
            'what', 'who', 'when', 'where', 'how', 'why', 
            'which', 'whose', 'whom'
        ]
        
        # Conjunction patterns for splitting
        self.split_patterns = [
            r' and ',
            r', and ',
            r'; ',
            r'\? ',
        ]
    
    def decompose(self, query: str) -> list:
        """
        Break query into atomic components
        
        Args:
            query: User's input query
            
        Returns:
            List of component dicts with metadata
        """
        if not query or len(query.strip()) < 3:
            return [self._create_component(query, priority='high')]
        
        query_lower = query.lower()
        
        # Detect if time-sensitive
        is_temporal = any(kw in query_lower for kw in self.temporal_patterns)
        
        # Split query into parts
        parts = self._split_query(query)
        
        # Create components
        components = []
        for i, part in enumerate(parts[:3]):  # Max 3 components
            component = self._create_component(
                part,
                priority='high' if len(parts) == 1 else 'medium',
                requires_web=is_temporal,
                cacheable=not is_temporal,
                index=i
            )
            components.append(component)
        
        logger.info(f"🔍 Decomposed '{query[:50]}...' into {len(components)} component(s)")
        return components
    
    def _split_query(self, query: str) -> list:
        """Split query on conjunctions and punctuation"""
        parts = [query]
        
        # Try each split pattern
        for pattern in self.split_patterns:
            new_parts = []
            for part in parts:
                split_parts = re.split(pattern, part, flags=re.IGNORECASE)
                new_parts.extend([p.strip() for p in split_parts if p.strip()])
            parts = new_parts
        
        return parts if parts else [query]
    
    def _create_component(self, query: str, priority='medium', 
                         requires_web=False, cacheable=True, index=0) -> dict:
        """Create component metadata"""
        return {
            'query': query.strip(),
            'priority': priority,
            'requires_web': requires_web,
            'cacheable': cacheable,
            'estimated_tokens': self._estimate_tokens(query),
            'index': index
        }
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token count estimate"""
        return int(len(text.split()) * 1.3)
