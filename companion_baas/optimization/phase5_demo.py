"""
Phase 5 Optimization Demo
=========================

Demonstrates all optimization features:
1. Performance profiling
2. Multi-level caching
3. Real-time monitoring
4. Query optimization
"""

import sys
sys.path.insert(0, '/home/aryan/Documents/Companion deepthink/companion_baas')

import time
import random
from optimization.profiler import profiler
from optimization.cache_optimizer import cache_optimizer
from optimization.monitoring import monitor, AlertLevel


def print_section(title: str):
    """Print section header"""
    print("\n" + "=" * 90)
    print(f"  {title}")
    print("=" * 90)


def print_subsection(title: str):
    """Print subsection header"""
    print(f"\n{title}")
    print("-" * 90)


# ============================================================================
# 1. PROFILING DEMO
# ============================================================================

@profiler.profile("expensive_operation")
def expensive_operation(n: int) -> int:
    """Simulated expensive operation"""
    time.sleep(0.01)  # Simulate work
    return sum(range(n))


@profiler.profile("fast_operation")
def fast_operation(x: int, y: int) -> int:
    """Fast operation"""
    return x + y


def demo_profiling():
    """Demonstrate performance profiling"""
    print_section("1. PERFORMANCE PROFILING")
    
    print("Running profiled operations...")
    
    # Run expensive operation multiple times
    with profiler.measure("expensive_batch"):
        for i in range(5):
            result = expensive_operation(1000)
    
    # Run fast operation many times
    with profiler.measure("fast_batch"):
        for i in range(100):
            result = fast_operation(i, i+1)
    
    # Get memory/CPU usage
    memory = profiler.get_memory_usage()
    cpu = profiler.get_cpu_usage()
    
    print(f"\n✓ Operations completed")
    print(f"  Memory: {memory['rss_mb']:.1f} MB (RSS)")
    print(f"  CPU: {cpu['percent']:.1f}%")
    
    # Generate report
    print("\nProfiling Report:")
    report = profiler.generate_report(sort_by='total_time')
    print(report)


# ============================================================================
# 2. CACHING DEMO
# ============================================================================

@cache_optimizer.cached(ttl=60, tier=1)
def fetch_user_data(user_id: int) -> dict:
    """Simulate fetching user data (expensive)"""
    time.sleep(0.01)  # Simulate database query
    return {
        "id": user_id,
        "name": f"User {user_id}",
        "email": f"user{user_id}@example.com"
    }


@cache_optimizer.cached(ttl=300, tier=2)
def fetch_analytics(date: str) -> dict:
    """Simulate fetching analytics (very expensive)"""
    time.sleep(0.05)  # Simulate complex query
    return {
        "date": date,
        "views": random.randint(1000, 10000),
        "clicks": random.randint(100, 1000)
    }


def demo_caching():
    """Demonstrate multi-level caching"""
    print_section("2. MULTI-LEVEL CACHING")
    
    print_subsection("Testing L1 Cache (Hot Data)")
    
    # First call - not cached
    start = time.perf_counter()
    data1 = fetch_user_data(1)
    uncached_time = time.perf_counter() - start
    print(f"✓ First call (uncached): {uncached_time*1000:.2f}ms")
    
    # Second call - cached
    start = time.perf_counter()
    data2 = fetch_user_data(1)
    cached_time = time.perf_counter() - start
    print(f"✓ Second call (cached): {cached_time*1000:.3f}ms")
    
    speedup = uncached_time / cached_time if cached_time > 0 else 0
    print(f"✓ Cache speedup: {speedup:.0f}x")
    
    print_subsection("Testing L2 Cache (Warm Data)")
    
    # Call multiple users (will be in L2)
    for i in range(1, 11):
        fetch_user_data(i)
    
    print("✓ Loaded 10 users into cache")
    
    print_subsection("Cache Warming")
    
    # Register keys for warming
    cache_optimizer.register_warmup(
        "analytics_2024_01",
        lambda: fetch_analytics("2024-01-01")
    )
    cache_optimizer.register_warmup(
        "analytics_2024_02",
        lambda: fetch_analytics("2024-02-01")
    )
    
    # Warm cache
    cache_optimizer.warm_cache()
    
    # Verify warmed data is cached
    start = time.perf_counter()
    data = fetch_analytics("2024-01-01")
    warmed_time = time.perf_counter() - start
    print(f"✓ Warmed data access: {warmed_time*1000:.3f}ms")
    
    print_subsection("Cache Statistics")
    
    stats = cache_optimizer.get_stats()
    
    print(f"\nL1 Cache (Hot):")
    print(f"  Size: {stats['l1']['size']}/{stats['l1']['max_size']}")
    print(f"  Hits: {stats['l1']['hits']}")
    print(f"  Misses: {stats['l1']['misses']}")
    print(f"  Hit Rate: {stats['l1']['hit_rate']:.1f}%")
    print(f"  Memory: {stats['l1']['total_size_mb']:.2f} MB")
    
    print(f"\nL2 Cache (Warm):")
    print(f"  Size: {stats['l2']['size']}/{stats['l2']['max_size']}")
    print(f"  Hits: {stats['l2']['hits']}")
    print(f"  Misses: {stats['l2']['misses']}")
    print(f"  Hit Rate: {stats['l2']['hit_rate']:.1f}%")
    print(f"  Memory: {stats['l2']['total_size_mb']:.2f} MB")
    
    print(f"\nCache Promotions:")
    print(f"  L2 → L1: {stats['l1_promotions']}")


# ============================================================================
# 3. MONITORING DEMO
# ============================================================================

def simulated_request(endpoint: str, duration: float, status: str = "success"):
    """Simulate an API request"""
    time.sleep(duration)
    monitor.record_request(endpoint, duration, status)


def demo_monitoring():
    """Demonstrate real-time monitoring"""
    print_section("3. REAL-TIME MONITORING")
    
    print_subsection("Simulating API Requests")
    
    # Simulate various requests
    endpoints = [
        ("/api/search", 0.02),
        ("/api/search", 0.03),
        ("/api/search", 0.025),
        ("/api/users", 0.01),
        ("/api/users", 0.015),
        ("/api/analytics", 0.05),
        ("/api/analytics", 0.045),
    ]
    
    for endpoint, duration in endpoints:
        simulated_request(endpoint, duration)
    
    print(f"✓ Simulated {len(endpoints)} requests")
    
    print_subsection("Cache Metrics")
    
    # Simulate cache hits/misses
    for i in range(20):
        if random.random() < 0.8:  # 80% hit rate
            monitor.record_cache_hit("user_cache")
        else:
            monitor.record_cache_miss("user_cache")
    
    hit_rate = monitor.get_cache_hit_rate("user_cache")
    print(f"✓ Cache hit rate: {hit_rate:.1f}%")
    
    print_subsection("System Metrics")
    
    # Record system metrics
    memory = profiler.get_memory_usage()
    cpu = profiler.get_cpu_usage()
    
    # Use correct key names from profiler
    memory_bytes = memory.get('rss_mb', 0) * 1024 * 1024  # Convert MB to bytes
    monitor.record_memory(memory_bytes)
    monitor.record_cpu(cpu.get('percent', 0))
    
    print(f"✓ Memory: {memory['rss_mb']:.1f} MB")
    print(f"✓ CPU: {cpu['percent']:.1f}%")
    
    print_subsection("Performance Statistics")
    
    # Get request stats
    for endpoint in ["/api/search", "/api/users", "/api/analytics"]:
        stats = monitor.get_request_stats(endpoint)
        if stats:
            print(f"\n{endpoint}:")
            print(f"  Count: {stats['count']}")
            print(f"  Avg: {stats['avg']*1000:.2f}ms")
            print(f"  P50: {stats['p50']*1000:.2f}ms")
            print(f"  P95: {stats['p95']*1000:.2f}ms")
            print(f"  P99: {stats['p99']*1000:.2f}ms")
    
    print_subsection("Alerts")
    
    # Check for alerts
    alerts = monitor.get_alerts()
    if alerts:
        print(f"\n⚠️  {len(alerts)} alerts generated:")
        for alert in alerts:
            print(f"  {alert}")
    else:
        print("\n✓ No alerts - system performing well")


# ============================================================================
# 4. INTEGRATION DEMO
# ============================================================================

@profiler.profile("integrated_operation")
@cache_optimizer.cached(ttl=60, tier=1)
def integrated_operation(user_id: int, query: str) -> dict:
    """Operation using both profiling and caching"""
    # Simulate search operation
    start = time.perf_counter()
    time.sleep(0.02)
    duration = time.perf_counter() - start
    
    # Record metrics
    monitor.record_request(f"/api/search?q={query}", duration)
    
    return {
        "user_id": user_id,
        "query": query,
        "results": [f"Result {i}" for i in range(10)]
    }


def demo_integration():
    """Demonstrate integrated optimization"""
    print_section("4. INTEGRATED OPTIMIZATION")
    
    print("Running integrated operations with profiling + caching + monitoring...")
    
    # First call - not cached
    print("\nFirst call (uncached):")
    start = time.perf_counter()
    result1 = integrated_operation(1, "python")
    time1 = time.perf_counter() - start
    print(f"  Time: {time1*1000:.2f}ms")
    print(f"  Results: {len(result1['results'])} items")
    
    # Second call - cached
    print("\nSecond call (cached):")
    start = time.perf_counter()
    result2 = integrated_operation(1, "python")
    time2 = time.perf_counter() - start
    print(f"  Time: {time2*1000:.3f}ms")
    print(f"  Speedup: {time1/time2:.0f}x")
    
    # Different query - not cached
    print("\nDifferent query (uncached):")
    start = time.perf_counter()
    result3 = integrated_operation(1, "javascript")
    time3 = time.perf_counter() - start
    print(f"  Time: {time3*1000:.2f}ms")
    
    print("\n✓ All operations tracked by profiling, caching, and monitoring")


# ============================================================================
# MAIN DEMO
# ============================================================================

def main():
    """Run complete Phase 5 optimization demo"""
    print("=" * 90)
    print("PHASE 5: OPTIMIZATION & PERFORMANCE TUNING")
    print("=" * 90)
    print("\nDemonstrating all optimization features...")
    
    start_time = time.time()
    
    # Run all demos
    demo_profiling()
    demo_caching()
    demo_monitoring()
    demo_integration()
    
    total_time = time.time() - start_time
    
    # Final summary
    print_section("OPTIMIZATION SUMMARY")
    
    print("\n✅ All optimization features demonstrated:")
    print("  1. ✓ Performance profiling with statistics")
    print("  2. ✓ Multi-level caching (L1/L2)")
    print("  3. ✓ Real-time monitoring with metrics")
    print("  4. ✓ Integrated optimization pipeline")
    
    print(f"\n✅ Total demo time: {total_time:.2f}s")
    
    # Generate monitoring report
    print("\n" + monitor.generate_report())
    
    print("\n" + "=" * 90)
    print("✅ Phase 5 optimization demo completed successfully!")
    print("=" * 90)


if __name__ == "__main__":
    main()
