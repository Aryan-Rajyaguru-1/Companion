"""
Research Agent - RAG-based knowledge retrieval for best practices
"""

import logging
from typing import Dict, Any, List, Optional
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ResearchAgent(BaseAgent):
    """Agent specialized in researching solutions using RAG"""
    
    def __init__(self, brain=None):
        super().__init__("ResearchAgent", brain)
        self.skills = [
            'find_best_practice',
            'search_similar_code',
            'get_documentation',
            'find_solution',
            'research_pattern'
        ]
        self.knowledge_base: List[Dict[str, Any]] = []
        self._initialize_knowledge_base()
    
    def _initialize_knowledge_base(self):
        """Initialize with common coding patterns and best practices"""
        self.knowledge_base = [
            {
                'pattern': 'error_handling',
                'description': 'Proper error handling with try-except',
                'code': '''try:
    result = risky_operation()
    return {'success': True, 'result': result}
except Exception as e:
    logger.error(f"Error: {e}")
    return {'success': False, 'error': str(e)}'''
            },
            {
                'pattern': 'async_function',
                'description': 'Async function with proper error handling',
                'code': '''async def async_operation(param: str) -> Dict[str, Any]:
    """Docstring explaining the function"""
    try:
        result = await some_async_call(param)
        return {'success': True, 'data': result}
    except Exception as e:
        logger.error(f"Async error: {e}")
        return {'success': False, 'error': str(e)}'''
            },
            {
                'pattern': 'logging',
                'description': 'Proper logging setup',
                'code': '''import logging

logger = logging.getLogger(__name__)

def function_with_logging():
    logger.info("Starting operation")
    try:
        # operation
        logger.debug("Debug info")
        logger.info("✅ Operation successful")
    except Exception as e:
        logger.error(f"❌ Operation failed: {e}")
        raise'''
            },
            {
                'pattern': 'type_hints',
                'description': 'Function with proper type hints',
                'code': '''from typing import Dict, Any, List, Optional

def typed_function(
    param1: str,
    param2: int,
    optional: Optional[str] = None
) -> Dict[str, Any]:
    """
    Function with complete type hints
    
    Args:
        param1: Description
        param2: Description
        optional: Optional parameter
        
    Returns:
        Dict with result
    """
    return {'param1': param1, 'param2': param2}'''
            },
            {
                'pattern': 'caching',
                'description': 'Simple caching decorator',
                'code': '''from functools import lru_cache

@lru_cache(maxsize=128)
def expensive_operation(param: str) -> str:
    """Cached expensive operation"""
    # expensive computation
    return result'''
            },
            {
                'pattern': 'retry_logic',
                'description': 'Retry with exponential backoff',
                'code': '''import time
from typing import Callable, Any

def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    backoff_factor: float = 2.0
) -> Any:
    """Retry function with exponential backoff"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait_time = backoff_factor ** attempt
            logger.warning(f"Retry {attempt + 1}/{max_retries} after {wait_time}s")
            time.sleep(wait_time)'''
            }
        ]
    
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a research task"""
        action = task.get('action')
        query = task.get('query', '')
        
        if action == 'find_best_practice':
            return await self.find_best_practice(query)
        elif action == 'find_solution':
            return await self.find_solution(task.get('problem'))
        elif action == 'search_pattern':
            return await self.search_pattern(query)
        else:
            return {
                'success': False,
                'error': f"Unknown action: {action}"
            }
    
    async def find_best_practice(self, topic: str) -> Dict[str, Any]:
        """Find best practice for a given topic"""
        try:
            # Search knowledge base
            results = []
            for item in self.knowledge_base:
                if topic.lower() in item['pattern'].lower() or \
                   topic.lower() in item['description'].lower():
                    results.append(item)
            
            if results:
                self.log_action('find_best_practice', f"Found {len(results)} patterns", {
                    'topic': topic
                })
                return {
                    'success': True,
                    'results': results
                }
            
            # If not in KB, use brain to research
            if self.brain:
                prompt = f"""Find best practices for: {topic}
                
Provide:
1. Description
2. Example code
3. Common pitfalls to avoid"""
                
                response = await self.think(prompt)
                
                self.log_action('find_best_practice', 'Researched with LLM', {
                    'topic': topic
                })
                
                return {
                    'success': True,
                    'research': response,
                    'source': 'llm'
                }
            
            return {
                'success': False,
                'error': 'No results found and no brain available'
            }
        except Exception as e:
            logger.error(f"❌ Research error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def find_solution(self, problem: str) -> Dict[str, Any]:
        """Find solution to a coding problem"""
        try:
            if not self.brain:
                return {
                    'success': False,
                    'error': 'Brain not available for research'
                }
            
            prompt = f"""Analyze this problem and provide a solution:

Problem: {problem}

Provide:
1. Root cause analysis
2. Solution approach
3. Example code
4. Testing strategy"""
            
            response = await self.think(prompt)
            
            self.log_action('find_solution', 'Generated solution', {
                'problem': problem[:100]
            })
            
            return {
                'success': True,
                'solution': response
            }
        except Exception as e:
            logger.error(f"❌ Find solution error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def search_pattern(self, pattern_name: str) -> Dict[str, Any]:
        """Search for a specific coding pattern"""
        try:
            for item in self.knowledge_base:
                if pattern_name.lower() == item['pattern'].lower():
                    self.log_action('search_pattern', f"Found: {pattern_name}")
                    return {
                        'success': True,
                        'pattern': item
                    }
            
            return {
                'success': False,
                'error': f"Pattern '{pattern_name}' not found"
            }
        except Exception as e:
            logger.error(f"❌ Search pattern error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def add_to_knowledge_base(self, pattern: Dict[str, Any]):
        """Add new pattern to knowledge base"""
        self.knowledge_base.append(pattern)
        logger.info(f"📚 Added pattern: {pattern.get('pattern')}")
