"""
Laptop-Optimized Neural Pipeline
Complete integration of decomposer, processor, and merger
Designed for Dell Latitude 7480 (8GB RAM, i7-7600U)
"""

import asyncio
import logging
from typing import Dict, Optional
from .query_decomposer import UltraLightDecomposer
from .micro_processor import CPUOptimizedProcessor
from .neural_merger import SimpleMerger
from .cache_manager import MemoryEfficientCache

logger = logging.getLogger(__name__)

class LaptopNeuralPipeline:
    """Complete neural processing pipeline for laptop deployment"""
    
    def __init__(self, llm_client, web_scraper, enable_neural=True):
        """
        Initialize neural pipeline
        
        Args:
            llm_client: OpenRouter API client
            web_scraper: Search engine wrapper
            enable_neural: Enable/disable neural processing
        """
        self.llm = llm_client
        self.web = web_scraper
        self.enabled = enable_neural
        
        # Initialize components
        self.decomposer = UltraLightDecomposer()
        self.cache = MemoryEfficientCache(max_size_mb=50, ttl=1800)
        self.processor = CPUOptimizedProcessor(llm_client, web_scraper, self.cache)
        self.merger = SimpleMerger()
        
        # Performance tracking
        self.total_queries = 0
        self.neural_processed = 0
        self.fallback_count = 0
        
        logger.info(f"🚀 Neural Pipeline initialized (enabled={enable_neural})")
    
    async def process_query(self, query: str, use_neural: bool = True) -> Dict:
        """
        Main query processing method
        
        Args:
            query: User's input query
            use_neural: Whether to use neural processing (can be disabled per query)
            
        Returns:
            Dict with response and metadata
        """
        self.total_queries += 1
        
        # Quick bypass for very simple queries
        if not self.enabled or not use_neural or len(query.split()) < 3:
            logger.info("⚡ Using simple processing (neural bypass)")
            return await self._simple_process(query)
        
        try:
            start_time = asyncio.get_event_loop().time()
            
            # Phase 1: Decompose query
            logger.info(f"📝 Processing: {query[:60]}...")
            components = self.decomposer.decompose(query)
            
            # Phase 2: Process components in parallel
            results = await asyncio.wait_for(
                self.processor.process_parallel(components),
                timeout=15.0  # Overall processing timeout
            )
            
            # Phase 3: Merge results
            if not results:
                logger.warning("No results from processor, using fallback")
                return await self._simple_process(query)
            
            if len(results) > 1:
                final_response = self.merger.synthesize(results, max_length=600)
            else:
                final_response = results[0].get('result', '')
            
            # Calculate stats
            elapsed = asyncio.get_event_loop().time() - start_time
            cache_hits = sum(1 for r in results if r.get('source') == 'cache')
            total_tokens = sum(r.get('tokens', 0) for r in results)
            
            self.neural_processed += 1
            
            logger.info(f"✅ Neural processing complete in {elapsed:.2f}s")
            
            return {
                'response': final_response,
                'metadata': {
                    'neural_processed': True,
                    'components': len(components),
                    'cache_hits': cache_hits,
                    'sources': [r.get('source') for r in results],
                    'processing_time': f"{elapsed:.2f}s",
                    'tokens_used': total_tokens,
                    'cache_stats': self.cache.get_stats()
                }
            }
            
        except asyncio.TimeoutError:
            logger.warning("⏱️ Neural pipeline timeout, using fallback")
            self.fallback_count += 1
            return await self._simple_process(query)
            
        except Exception as e:
            logger.error(f"❌ Neural pipeline error: {e}")
            self.fallback_count += 1
            return await self._simple_process(query)
    
    async def _simple_process(self, query: str) -> Dict:
        """
        Simple processing fallback (no neural layer)
        
        Args:
            query: User's input query
            
        Returns:
            Dict with response or None to use existing backend
        """
        # Check cache first
        cached = self.cache.get(query)
        if cached:
            logger.info("✅ Cache hit (fallback mode)")
            return {
                'response': cached,
                'metadata': {
                    'neural_processed': False,
                    'source': 'cache_fallback'
                }
            }
        
        # Return None to let existing backend handle it
        return {
            'response': None,
            'metadata': {
                'neural_processed': False,
                'source': 'bypass'
            }
        }
    
    def get_statistics(self) -> Dict:
        """Get pipeline performance statistics"""
        neural_rate = (self.neural_processed / self.total_queries * 100) if self.total_queries > 0 else 0
        
        return {
            'total_queries': self.total_queries,
            'neural_processed': self.neural_processed,
            'fallback_count': self.fallback_count,
            'neural_rate': f"{neural_rate:.1f}%",
            'cache_stats': self.cache.get_stats(),
            'enabled': self.enabled
        }
    
    def clear_cache(self):
        """Clear the cache"""
        self.cache.clear()
        logger.info("🗑️ Pipeline cache cleared")
    
    def enable(self):
        """Enable neural processing"""
        self.enabled = True
        logger.info("✅ Neural processing enabled")
    
    def disable(self):
        """Disable neural processing"""
        self.enabled = False
        logger.info("⏸️ Neural processing disabled")
