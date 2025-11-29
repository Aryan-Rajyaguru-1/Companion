"""
Performance Profiler - Phase 5: Optimization

Comprehensive performance profiling tool for all system components.
"""

import time
import functools
import psutil
import os
from typing import Callable, Any, Dict, List
from dataclasses import dataclass, field
from collections import defaultdict
import statistics


@dataclass
class ProfileResult:
    """Result of a profiling operation"""
    name: str
    calls: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    avg_time: float = 0.0
    times: List[float] = field(default_factory=list)
    
    def update(self, duration: float):
        """Update statistics with new timing"""
        self.calls += 1
        self.total_time += duration
        self.min_time = min(self.min_time, duration)
        self.max_time = max(self.max_time, duration)
        self.times.append(duration)
        self.avg_time = self.total_time / self.calls
    
    def get_percentile(self, percentile: int) -> float:
        """Get percentile value (50, 95, 99)"""
        if not self.times:
            return 0.0
        sorted_times = sorted(self.times)
        index = int(len(sorted_times) * percentile / 100)
        return sorted_times[min(index, len(sorted_times) - 1)]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics"""
        if not self.times:
            return {}
        
        return {
            'name': self.name,
            'calls': self.calls,
            'total_time': f"{self.total_time:.4f}s",
            'avg_time': f"{self.avg_time*1000:.2f}ms",
            'min_time': f"{self.min_time*1000:.2f}ms",
            'max_time': f"{self.max_time*1000:.2f}ms",
            'p50': f"{self.get_percentile(50)*1000:.2f}ms",
            'p95': f"{self.get_percentile(95)*1000:.2f}ms",
            'p99': f"{self.get_percentile(99)*1000:.2f}ms",
            'stddev': f"{statistics.stdev(self.times)*1000:.2f}ms" if len(self.times) > 1 else "N/A"
        }


class PerformanceProfiler:
    """
    Performance profiler for measuring execution times
    
    Features:
    - Function timing decorator
    - Memory usage tracking
    - CPU usage tracking
    - Statistical analysis
    - Report generation
    """
    
    def __init__(self):
        """Initialize profiler"""
        self.results: Dict[str, ProfileResult] = defaultdict(lambda: ProfileResult(name="unknown"))
        self.enabled = True
        self.process = psutil.Process(os.getpid())
    
    def profile(self, name: str = None):
        """
        Decorator to profile a function
        
        Usage:
            @profiler.profile("my_function")
            def my_function():
                pass
        """
        def decorator(func: Callable) -> Callable:
            func_name = name or func.__name__
            
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                if not self.enabled:
                    return func(*args, **kwargs)
                
                # Measure execution time
                start_time = time.perf_counter()
                result = func(*args, **kwargs)
                duration = time.perf_counter() - start_time
                
                # Update statistics
                self.results[func_name].name = func_name
                self.results[func_name].update(duration)
                
                return result
            
            return wrapper
        
        return decorator
    
    def measure(self, name: str):
        """
        Context manager for measuring code blocks
        
        Usage:
            with profiler.measure("database_query"):
                # code to measure
                pass
        """
        return ProfileContext(self, name)
    
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage"""
        mem_info = self.process.memory_info()
        return {
            'rss_mb': mem_info.rss / 1024 / 1024,  # Resident Set Size
            'vms_mb': mem_info.vms / 1024 / 1024,  # Virtual Memory Size
            'percent': self.process.memory_percent()
        }
    
    def get_cpu_usage(self) -> Dict[str, float]:
        """Get current CPU usage"""
        return {
            'percent': self.process.cpu_percent(interval=0.1),
            'num_threads': self.process.num_threads()
        }
    
    def get_result(self, name: str) -> ProfileResult:
        """Get profiling result for a specific function"""
        return self.results.get(name)
    
    def get_all_results(self) -> Dict[str, ProfileResult]:
        """Get all profiling results"""
        return dict(self.results)
    
    def clear(self):
        """Clear all profiling data"""
        self.results.clear()
    
    def enable(self):
        """Enable profiling"""
        self.enabled = True
    
    def disable(self):
        """Disable profiling"""
        self.enabled = False
    
    def generate_report(self, sort_by: str = 'total_time') -> str:
        """
        Generate a profiling report
        
        Args:
            sort_by: Sort results by ('total_time', 'avg_time', 'calls', 'max_time')
        
        Returns:
            Formatted report string
        """
        if not self.results:
            return "No profiling data available"
        
        # Sort results
        sort_key_map = {
            'total_time': lambda x: x[1].total_time,
            'avg_time': lambda x: x[1].avg_time,
            'calls': lambda x: x[1].calls,
            'max_time': lambda x: x[1].max_time,
        }
        
        sort_key = sort_key_map.get(sort_by, sort_key_map['total_time'])
        sorted_results = sorted(self.results.items(), key=sort_key, reverse=True)
        
        # Build report
        lines = []
        lines.append("=" * 100)
        lines.append("PERFORMANCE PROFILING REPORT")
        lines.append("=" * 100)
        
        # System info
        mem_usage = self.get_memory_usage()
        cpu_usage = self.get_cpu_usage()
        
        lines.append(f"\nSystem Resources:")
        lines.append(f"  Memory: {mem_usage['rss_mb']:.1f} MB (RSS), {mem_usage['vms_mb']:.1f} MB (VMS)")
        lines.append(f"  CPU: {cpu_usage['percent']:.1f}%, Threads: {cpu_usage['num_threads']}")
        
        # Function statistics
        lines.append(f"\nFunction Statistics (sorted by {sort_by}):")
        lines.append("-" * 100)
        
        # Header
        header = f"{'Function':<30} {'Calls':>8} {'Total':>12} {'Avg':>10} {'Min':>10} {'Max':>10} {'P95':>10} {'StdDev':>10}"
        lines.append(header)
        lines.append("-" * 100)
        
        # Results
        for func_name, result in sorted_results:
            stats = result.get_stats()
            line = (
                f"{func_name:<30} "
                f"{stats['calls']:>8} "
                f"{stats['total_time']:>12} "
                f"{stats['avg_time']:>10} "
                f"{stats['min_time']:>10} "
                f"{stats['max_time']:>10} "
                f"{stats['p95']:>10} "
                f"{stats['stddev']:>10}"
            )
            lines.append(line)
        
        lines.append("-" * 100)
        
        # Summary
        total_calls = sum(r.calls for r in self.results.values())
        total_time = sum(r.total_time for r in self.results.values())
        
        lines.append(f"\nSummary:")
        lines.append(f"  Total functions profiled: {len(self.results)}")
        lines.append(f"  Total calls: {total_calls}")
        lines.append(f"  Total time: {total_time:.4f}s")
        lines.append("=" * 100)
        
        return "\n".join(lines)
    
    def get_slowest_functions(self, limit: int = 10) -> List[tuple]:
        """Get slowest functions by average time"""
        sorted_results = sorted(
            self.results.items(),
            key=lambda x: x[1].avg_time,
            reverse=True
        )
        return sorted_results[:limit]
    
    def get_most_called_functions(self, limit: int = 10) -> List[tuple]:
        """Get most frequently called functions"""
        sorted_results = sorted(
            self.results.items(),
            key=lambda x: x[1].calls,
            reverse=True
        )
        return sorted_results[:limit]


class ProfileContext:
    """Context manager for profiling code blocks"""
    
    def __init__(self, profiler: PerformanceProfiler, name: str):
        self.profiler = profiler
        self.name = name
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.perf_counter() - self.start_time
        self.profiler.results[self.name].name = self.name
        self.profiler.results[self.name].update(duration)


# Global profiler instance
profiler = PerformanceProfiler()


# Example usage and tests
if __name__ == "__main__":
    print("=" * 100)
    print("PERFORMANCE PROFILER - Testing")
    print("=" * 100)
    
    # Test 1: Decorator profiling
    print("\nTest 1: Decorator Profiling")
    
    @profiler.profile("fast_function")
    def fast_function(n: int) -> int:
        """Fast function"""
        return sum(range(n))
    
    @profiler.profile("slow_function")
    def slow_function(n: int) -> int:
        """Slow function with sleep"""
        time.sleep(0.01)
        return sum(range(n))
    
    # Call functions multiple times
    for i in range(10):
        fast_function(1000)
        slow_function(100)
    
    print("✓ Executed 10 calls each of fast and slow functions")
    
    # Test 2: Context manager profiling
    print("\nTest 2: Context Manager Profiling")
    
    for i in range(5):
        with profiler.measure("custom_block"):
            time.sleep(0.005)
            result = sum(range(10000))
    
    print("✓ Measured 5 custom code blocks")
    
    # Test 3: Get specific results
    print("\nTest 3: Specific Function Stats")
    fast_stats = profiler.get_result("fast_function").get_stats()
    print(f"Fast Function: {fast_stats}")
    
    # Test 4: Memory and CPU
    print("\nTest 4: System Resources")
    mem = profiler.get_memory_usage()
    cpu = profiler.get_cpu_usage()
    print(f"Memory: {mem['rss_mb']:.1f} MB")
    print(f"CPU: {cpu['percent']:.1f}%")
    
    # Test 5: Generate report
    print("\nTest 5: Full Report")
    report = profiler.generate_report(sort_by='avg_time')
    print(report)
    
    # Test 6: Slowest functions
    print("\nTest 6: Slowest Functions")
    slowest = profiler.get_slowest_functions(limit=3)
    for func_name, result in slowest:
        print(f"  {func_name}: {result.avg_time*1000:.2f}ms avg")
    
    # Test 7: Most called functions
    print("\nTest 7: Most Called Functions")
    most_called = profiler.get_most_called_functions(limit=3)
    for func_name, result in most_called:
        print(f"  {func_name}: {result.calls} calls")
