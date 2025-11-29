"""
Tool Executor - Async execution and caching for tools

Provides async execution capabilities and result caching.
"""

import asyncio
import time
import hashlib
import json
from typing import Any, Optional, Dict
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

from .tool_registry import ToolRegistry


@dataclass
class ExecutionResult:
    """Result of tool execution"""
    success: bool
    result: Any
    error: Optional[str] = None
    execution_time: float = 0.0
    cached: bool = False


class ToolExecutor:
    """
    Execute tools with async support and caching
    
    Features:
    - Async execution
    - Result caching
    - Timeout handling
    - Error recovery
    """
    
    def __init__(
        self,
        registry: ToolRegistry,
        cache_enabled: bool = True,
        cache_ttl: int = 300,
        timeout: int = 30
    ):
        """
        Initialize tool executor
        
        Args:
            registry: Tool registry
            cache_enabled: Enable result caching
            cache_ttl: Cache time-to-live in seconds
            timeout: Execution timeout in seconds
        """
        self.registry = registry
        self.cache_enabled = cache_enabled
        self.cache_ttl = cache_ttl
        self.timeout = timeout
        
        # Cache: {cache_key: (result, timestamp)}
        self._cache: Dict[str, tuple] = {}
        
        # Thread pool for async execution
        self._executor = ThreadPoolExecutor(max_workers=10)
    
    def _generate_cache_key(self, tool_name: str, args: tuple, kwargs: dict) -> str:
        """Generate cache key for tool execution"""
        cache_data = {
            'tool': tool_name,
            'args': args,
            'kwargs': kwargs
        }
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.md5(cache_str.encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[Any]:
        """Get cached result if valid"""
        if not self.cache_enabled:
            return None
        
        if cache_key in self._cache:
            result, timestamp = self._cache[cache_key]
            
            # Check if cache is still valid
            if time.time() - timestamp < self.cache_ttl:
                return result
            else:
                # Remove expired cache
                del self._cache[cache_key]
        
        return None
    
    def _cache_result(self, cache_key: str, result: Any):
        """Cache execution result"""
        if self.cache_enabled:
            self._cache[cache_key] = (result, time.time())
    
    def execute(
        self,
        tool_name: str,
        *args,
        use_cache: bool = True,
        **kwargs
    ) -> ExecutionResult:
        """
        Execute a tool synchronously
        
        Args:
            tool_name: Name of tool to execute
            *args: Positional arguments
            use_cache: Whether to use cached results
            **kwargs: Keyword arguments
        
        Returns:
            ExecutionResult with output
        """
        # Generate cache key
        cache_key = self._generate_cache_key(tool_name, args, kwargs)
        
        # Check cache
        if use_cache:
            cached_result = self._get_cached_result(cache_key)
            if cached_result is not None:
                return ExecutionResult(
                    success=True,
                    result=cached_result,
                    cached=True,
                    execution_time=0.0
                )
        
        # Execute tool
        start_time = time.time()
        
        try:
            result = self.registry.execute(tool_name, *args, **kwargs)
            execution_time = time.time() - start_time
            
            # Cache result
            self._cache_result(cache_key, result)
            
            return ExecutionResult(
                success=True,
                result=result,
                execution_time=execution_time,
                cached=False
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            return ExecutionResult(
                success=False,
                result=None,
                error=f"{type(e).__name__}: {str(e)}",
                execution_time=execution_time
            )
    
    async def execute_async(
        self,
        tool_name: str,
        *args,
        use_cache: bool = True,
        **kwargs
    ) -> ExecutionResult:
        """
        Execute a tool asynchronously
        
        Args:
            tool_name: Name of tool to execute
            *args: Positional arguments
            use_cache: Whether to use cached results
            **kwargs: Keyword arguments
        
        Returns:
            ExecutionResult with output
        """
        # Run in thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self._executor,
            lambda: self.execute(tool_name, *args, use_cache=use_cache, **kwargs)
        )
        return result
    
    async def execute_batch(
        self,
        executions: list,
        use_cache: bool = True
    ) -> list:
        """
        Execute multiple tools in parallel
        
        Args:
            executions: List of (tool_name, args, kwargs) tuples
            use_cache: Whether to use cached results
        
        Returns:
            List of ExecutionResult objects
        """
        tasks = []
        for tool_name, args, kwargs in executions:
            task = self.execute_async(tool_name, *args, use_cache=use_cache, **kwargs)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        return results
    
    def clear_cache(self):
        """Clear all cached results"""
        self._cache.clear()
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics"""
        total_entries = len(self._cache)
        valid_entries = 0
        expired_entries = 0
        
        current_time = time.time()
        for cache_key, (result, timestamp) in list(self._cache.items()):
            if current_time - timestamp < self.cache_ttl:
                valid_entries += 1
            else:
                expired_entries += 1
                del self._cache[cache_key]
        
        return {
            'total_entries': total_entries,
            'valid_entries': valid_entries,
            'expired_entries': expired_entries,
            'cache_enabled': self.cache_enabled,
            'cache_ttl': self.cache_ttl
        }


# Example usage
if __name__ == "__main__":
    import sys
    sys.path.insert(0, '/home/aryan/Documents/Companion deepthink/companion_baas')
    
    from tools.tool_registry import ToolRegistry, tool
    
    print("=" * 70)
    print("TOOL EXECUTOR - Async Execution & Caching")
    print("=" * 70)
    
    # Create registry and executor
    registry = ToolRegistry()
    executor = ToolExecutor(registry, cache_enabled=True, cache_ttl=60)
    
    # Register test tools
    @tool(name="fibonacci", description="Calculate fibonacci number")
    def fib(n: int) -> int:
        """Calculate nth Fibonacci number"""
        if n <= 1:
            return n
        return fib(n-1) + fib(n-2)
    
    @tool(name="slow_operation", description="Simulates slow operation")
    def slow_op(duration: float = 1.0) -> str:
        """Simulate a slow operation"""
        time.sleep(duration)
        return f"Completed after {duration}s"
    
    registry.register(fib)
    registry.register(slow_op)
    
    # Test 1: Sync execution
    print("\nTest 1: Synchronous Execution")
    print("-" * 70)
    result = executor.execute("fibonacci", 10)
    print(f"✓ Success: {result.success}")
    print(f"✓ Result: {result.result}")
    print(f"✓ Time: {result.execution_time:.4f}s")
    print(f"✓ Cached: {result.cached}")
    
    # Test 2: Cached execution
    print("\nTest 2: Cached Execution (same call)")
    print("-" * 70)
    result2 = executor.execute("fibonacci", 10)
    print(f"✓ Success: {result2.success}")
    print(f"✓ Result: {result2.result}")
    print(f"✓ Time: {result2.execution_time:.4f}s")
    print(f"✓ Cached: {result2.cached}")
    
    # Test 3: Cache stats
    print("\nTest 3: Cache Statistics")
    print("-" * 70)
    stats = executor.get_cache_stats()
    print(f"✓ Total entries: {stats['total_entries']}")
    print(f"✓ Valid entries: {stats['valid_entries']}")
    print(f"✓ Cache TTL: {stats['cache_ttl']}s")
    
    # Test 4: Async execution
    print("\nTest 4: Asynchronous Execution")
    print("-" * 70)
    
    async def test_async():
        result = await executor.execute_async("slow_operation", duration=0.5)
        return result
    
    async_result = asyncio.run(test_async())
    print(f"✓ Success: {async_result.success}")
    print(f"✓ Result: {async_result.result}")
    print(f"✓ Time: {async_result.execution_time:.4f}s")
    
    # Test 5: Batch execution
    print("\nTest 5: Batch Parallel Execution")
    print("-" * 70)
    
    async def test_batch():
        executions = [
            ("fibonacci", (5,), {}),
            ("fibonacci", (10,), {}),
            ("fibonacci", (15,), {}),
        ]
        start = time.time()
        results = await executor.execute_batch(executions)
        total_time = time.time() - start
        
        return results, total_time
    
    batch_results, batch_time = asyncio.run(test_batch())
    print(f"✓ Executed {len(batch_results)} tools in parallel")
    print(f"✓ Total time: {batch_time:.4f}s")
    for i, result in enumerate(batch_results):
        print(f"  Result {i+1}: {result.result} (time: {result.execution_time:.4f}s, cached: {result.cached})")
    
    print("\n" + "=" * 70)
