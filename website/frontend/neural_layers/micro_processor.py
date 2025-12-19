"""
CPU-Optimized Micro Processor
Parallel processing with strict concurrency limits
Optimized for dual-core i7-7600U (2 workers max)
"""

import asyncio
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class CPUOptimizedProcessor:
    """Lightweight parallel processor for query components"""
    
    def __init__(self, llm_client, web_scraper, cache):
        """
        Initialize processor
        
        Args:
            llm_client: OpenRouter API client
            web_scraper: Search engine wrapper
            cache: Memory-efficient cache
        """
        self.llm = llm_client
        self.web = web_scraper
        self.cache = cache
        self.max_workers = 2  # Match physical cores
        
        logger.info(f"⚙️ Processor initialized: {self.max_workers} workers")
    
    async def process_component(self, component: Dict) -> Dict:
        """
        Process single query component
        
        Args:
            component: Component dict with query and metadata
            
        Returns:
            Result dict with response and metadata
        """
        query = component['query']
        
        # Check cache first
        cached = self.cache.get(query)
        if cached:
            logger.info(f"✅ Cache hit: {query[:40]}...")
            return {
                'query': query,
                'result': cached,
                'source': 'cache',
                'tokens': 0,
                'success': True
            }
        
        try:
            # Smart routing: Web OR LLM, not both (save resources)
            if component['requires_web']:
                # Time-sensitive → Web search only
                result = await asyncio.wait_for(
                    self._fetch_web_data(query),
                    timeout=5.0
                )
                source = 'web'
                tokens = 0
            else:
                # General knowledge → LLM only
                max_tokens = min(150, component.get('estimated_tokens', 100))
                result = await asyncio.wait_for(
                    self._fetch_llm_data(query, max_tokens),
                    timeout=8.0
                )
                source = 'llm'
                tokens = max_tokens
            
            # Cache if successful and cacheable
            if result and component['cacheable'] and len(result) > 20:
                self.cache.set(query, result)
            
            logger.info(f"✅ Processed via {source}: {query[:40]}...")
            
            return {
                'query': query,
                'result': result,
                'source': source,
                'tokens': tokens,
                'success': True
            }
            
        except asyncio.TimeoutError:
            logger.warning(f"⏱️ Timeout: {query[:40]}...")
            return {
                'query': query,
                'result': '',
                'source': 'timeout',
                'tokens': 0,
                'success': False
            }
        except Exception as e:
            logger.error(f"❌ Error processing '{query[:40]}...': {str(e)[:100]}")
            return {
                'query': query,
                'result': '',
                'source': 'error',
                'tokens': 0,
                'success': False,
                'error': str(e)
            }
    
    async def _fetch_web_data(self, query: str) -> str:
        """Fetch data from web scraper"""
        try:
            results = await asyncio.to_thread(
                self.web.multi_engine_search,
                query,
                max_results=5,
                include_content=False  # Skip heavy content scraping
            )
            
            if not results:
                return ""
            
            # Extract top snippets
            snippets = [r.snippet for r in results[:3] if r.snippet]
            return ' '.join(snippets[:2])  # Max 2 snippets
            
        except Exception as e:
            logger.error(f"Web fetch error: {e}")
            return ""
    
    async def _fetch_llm_data(self, query: str, max_tokens: int) -> str:
        """Fetch data from LLM"""
        try:
            # Use existing API wrapper (no max_tokens parameter support)
            response = await asyncio.to_thread(
                self.llm.generate_response,
                query,
                category='general'
            )
            
            # Extract content from response
            if isinstance(response, dict):
                content = response.get('response', response.get('content', ''))
            elif hasattr(response, 'content'):
                content = response.content
            else:
                content = str(response)
            
            # Clean special tokens and artifacts
            import re
            # Remove token markers
            content = re.sub(r'<[｜|]\s*\w+[▁_]\w+[▁_]*\w*\s*[｜|]>', '', content)
            content = re.sub(r'<\|begin_of_sentence\|>', '', content)
            content = re.sub(r'<\|end_of_sentence\|>', '', content)
            # Remove APIResponse wrapper if present
            content = re.sub(r'APIResponse\(.*?content=\'(.*?)\'.*?\)', r'\1', content, flags=re.DOTALL)
            
            return content.strip()
        except Exception as e:
            logger.error(f"LLM fetch error: {e}")
            return ""
    
    async def process_parallel(self, components: List[Dict]) -> List[Dict]:
        """
        Process multiple components in parallel with concurrency limit
        
        Args:
            components: List of component dicts
            
        Returns:
            List of result dicts
        """
        if not components:
            return []
        
        logger.info(f"🔄 Processing {len(components)} components...")
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.max_workers)
        
        async def bounded_process(comp):
            async with semaphore:
                return await self.process_component(comp)
        
        # Process all components
        results = await asyncio.gather(*[bounded_process(c) for c in components])
        
        # Filter successful results
        successful = [r for r in results if r.get('success')]
        failed = len(results) - len(successful)
        
        if failed > 0:
            logger.warning(f"⚠️ {failed} component(s) failed")
        
        logger.info(f"✅ Processed {len(successful)}/{len(components)} successfully")
        
        return successful
