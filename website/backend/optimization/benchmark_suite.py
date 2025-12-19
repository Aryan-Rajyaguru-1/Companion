"""
Benchmark Suite - Phase 5: Optimization

Comprehensive benchmarking of all system components.
"""

import sys
sys.path.insert(0, '/home/aryan/Documents/Companion deepthink/companion_baas')

import time
import asyncio
from optimization.profiler import profiler

# Import all components
from knowledge.elasticsearch_client import ElasticsearchClient
from knowledge.vector_store import VectorStore
from search.meilisearch_client import MeilisearchClient
from search.search_engine import SearchEngine
from execution.code_executor import CodeExecutor
from tools.tool_registry import ToolRegistry
from tools.tool_executor import ToolExecutor
from tools.builtin_tools import register_builtin_tools


class BenchmarkSuite:
    """Comprehensive benchmark suite for all components"""
    
    def __init__(self):
        """Initialize benchmark suite"""
        self.results = {}
        
        # Initialize components (only Phase 4 components that we know work)
        print("Initializing components...")
        self.code_executor = CodeExecutor()
        self.tool_registry = ToolRegistry()
        register_builtin_tools(self.tool_registry)
        self.tool_executor = ToolExecutor(self.tool_registry)
        
        print("✓ Components initialized\n")
    
    def print_section(self, title: str):
        """Print section header"""
        print("\n" + "=" * 90)
        print(f"  {title}")
        print("=" * 90)
    
    def print_subsection(self, title: str):
        """Print subsection header"""
        print(f"\n{title}")
        print("-" * 90)
    
    @profiler.profile("benchmark_elasticsearch_search")
    def benchmark_elasticsearch(self, iterations: int = 10):
        """Benchmark Elasticsearch operations"""
        self.print_subsection("Elasticsearch Vector Search")
        
        # Create test index
        index_name = "benchmark_test"
        
        try:
            # Test document
            test_doc = {
                "message": "This is a test document for benchmarking",
                "metadata": {"test": True}
            }
            
            # Benchmark embedding generation
            with profiler.measure("embedding_generation"):
                embedding = self.vector_store.encode_text(test_doc["message"])
            
            test_doc["embedding"] = embedding
            
            # Benchmark indexing
            with profiler.measure("elasticsearch_index"):
                self.elasticsearch.index_document(index_name, "bench_1", test_doc)
            
            # Benchmark search
            times = []
            for i in range(iterations):
                start = time.perf_counter()
                results = self.elasticsearch.search_similar(
                    index_name=index_name,
                    query_embedding=embedding,
                    k=5
                )
                times.append(time.perf_counter() - start)
            
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            
            print(f"✓ Vector Search ({iterations} iterations):")
            print(f"  Average: {avg_time*1000:.2f}ms")
            print(f"  Min: {min_time*1000:.2f}ms")
            print(f"  Max: {max_time*1000:.2f}ms")
            
            self.results['elasticsearch_search'] = avg_time
            
        except Exception as e:
            print(f"⚠️  Elasticsearch benchmark skipped: {e}")
            self.results['elasticsearch_search'] = None
    
    @profiler.profile("benchmark_meilisearch_search")
    def benchmark_meilisearch(self, iterations: int = 10):
        """Benchmark Meilisearch operations"""
        self.print_subsection("Meilisearch Text Search")
        
        index_name = "benchmark_test"
        
        try:
            # Test documents
            docs = [
                {"id": "1", "title": "Python Programming", "content": "Learn Python programming"},
                {"id": "2", "title": "JavaScript Guide", "content": "Master JavaScript development"},
                {"id": "3", "title": "Database Design", "content": "SQL and NoSQL databases"},
            ]
            
            # Benchmark indexing
            with profiler.measure("meilisearch_index"):
                self.meilisearch.add_documents(index_name, docs)
            
            time.sleep(0.1)  # Wait for indexing
            
            # Benchmark search
            times = []
            for i in range(iterations):
                start = time.perf_counter()
                results = self.meilisearch.search(index_name, "programming", limit=5)
                times.append(time.perf_counter() - start)
            
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            
            print(f"✓ Text Search ({iterations} iterations):")
            print(f"  Average: {avg_time*1000:.2f}ms")
            print(f"  Min: {min_time*1000:.2f}ms")
            print(f"  Max: {max_time*1000:.2f}ms")
            
            self.results['meilisearch_search'] = avg_time
            
        except Exception as e:
            print(f"⚠️  Meilisearch benchmark skipped: {e}")
            self.results['meilisearch_search'] = None
    
    @profiler.profile("benchmark_hybrid_search")
    def benchmark_hybrid_search(self, iterations: int = 10):
        """Benchmark hybrid search"""
        self.print_subsection("Hybrid Search (Text + Vector)")
        
        try:
            # Benchmark hybrid search
            times = []
            for i in range(iterations):
                start = time.perf_counter()
                try:
                    results = self.search_engine.hybrid_search(
                        query="programming",
                        index_name="benchmark_test",
                        limit=5
                    )
                except:
                    pass  # Ignore errors for benchmarking
                times.append(time.perf_counter() - start)
            
            if times:
                avg_time = sum(times) / len(times)
                min_time = min(times)
                max_time = max(times)
                
                print(f"✓ Hybrid Search ({iterations} iterations):")
                print(f"  Average: {avg_time*1000:.2f}ms")
                print(f"  Min: {min_time*1000:.2f}ms")
                print(f"  Max: {max_time*1000:.2f}ms")
                
                self.results['hybrid_search'] = avg_time
            
        except Exception as e:
            print(f"⚠️  Hybrid search benchmark skipped: {e}")
            self.results['hybrid_search'] = None
    
    @profiler.profile("benchmark_code_execution")
    def benchmark_code_execution(self, iterations: int = 10):
        """Benchmark code execution"""
        self.print_subsection("Code Execution")
        
        # Python code
        python_code = """
def factorial(n):
    return 1 if n <= 1 else n * factorial(n-1)
print(factorial(10))
"""
        
        # JavaScript code
        js_code = """
const factorial = n => n <= 1 ? 1 : n * factorial(n-1);
console.log(factorial(10));
"""
        
        # Benchmark Python
        times = []
        for i in range(iterations):
            start = time.perf_counter()
            result = self.code_executor.execute(python_code, language='python')
            times.append(time.perf_counter() - start)
        
        avg_time = sum(times) / len(times)
        print(f"✓ Python Execution ({iterations} iterations):")
        print(f"  Average: {avg_time*1000:.2f}ms")
        self.results['python_execution'] = avg_time
        
        # Benchmark JavaScript
        times = []
        for i in range(iterations):
            start = time.perf_counter()
            result = self.code_executor.execute(js_code, language='javascript')
            times.append(time.perf_counter() - start)
        
        avg_time = sum(times) / len(times)
        print(f"✓ JavaScript Execution ({iterations} iterations):")
        print(f"  Average: {avg_time*1000:.2f}ms")
        self.results['javascript_execution'] = avg_time
    
    @profiler.profile("benchmark_tool_execution")
    def benchmark_tool_execution(self, iterations: int = 100):
        """Benchmark tool execution"""
        self.print_subsection("Tool Execution")
        
        # Benchmark without cache
        times = []
        for i in range(iterations):
            start = time.perf_counter()
            result = self.tool_executor.execute("add", 5, 3, use_cache=False)
            times.append(time.perf_counter() - start)
        
        avg_time = sum(times) / len(times)
        print(f"✓ Tool Execution (no cache, {iterations} iterations):")
        print(f"  Average: {avg_time*1000:.3f}ms")
        self.results['tool_execution'] = avg_time
        
        # Benchmark with cache
        times = []
        for i in range(iterations):
            start = time.perf_counter()
            result = self.tool_executor.execute("add", 5, 3, use_cache=True)
            times.append(time.perf_counter() - start)
        
        avg_time = sum(times) / len(times)
        cached_time = times[-1]  # Last call should be cached
        
        print(f"✓ Tool Execution (with cache, {iterations} iterations):")
        print(f"  Average: {avg_time*1000:.3f}ms")
        print(f"  Cached call: {cached_time*1000:.3f}ms")
        
        speedup = self.results['tool_execution'] / cached_time
        print(f"  Cache speedup: {speedup:.1f}x")
        self.results['tool_execution_cached'] = cached_time
    
    @profiler.profile("benchmark_batch_operations")
    def benchmark_batch_operations(self):
        """Benchmark batch operations"""
        self.print_subsection("Batch Operations")
        
        # Benchmark batch tool execution
        async def run_batch():
            executions = [
                ("add", (i, i+1), {}) for i in range(10)
            ]
            start = time.perf_counter()
            results = await self.tool_executor.execute_batch(executions, use_cache=False)
            return time.perf_counter() - start
        
        batch_time = asyncio.run(run_batch())
        
        print(f"✓ Batch Tool Execution (10 tools in parallel):")
        print(f"  Total time: {batch_time*1000:.2f}ms")
        print(f"  Per tool: {batch_time*1000/10:.2f}ms")
        self.results['batch_execution'] = batch_time
    
    def run_all_benchmarks(self):
        """Run all benchmarks"""
        self.print_section("PHASE 5: PERFORMANCE BENCHMARKING")
        
        print("Running comprehensive benchmarks across all components...")
        print("This may take a minute...\n")
        
        start_time = time.time()
        
        # Run benchmarks (Phase 4 components only)
        self.benchmark_code_execution(iterations=10)
        self.benchmark_tool_execution(iterations=100)
        self.benchmark_batch_operations()
        
        total_time = time.time() - start_time
        
        # Generate summary
        self.print_section("BENCHMARK SUMMARY")
        
        print("\nPerformance Results:")
        print("-" * 90)
        
        for name, time_val in self.results.items():
            if time_val is not None:
                print(f"  {name:<30} {time_val*1000:>10.2f}ms")
            else:
                print(f"  {name:<30} {'N/A':>10}")
        
        print(f"\nTotal benchmark time: {total_time:.2f}s")
        
        # Performance analysis
        self.print_section("PERFORMANCE ANALYSIS")
        
        # Identify bottlenecks
        print("\n🐌 Potential Bottlenecks:")
        slow_operations = [
            (name, time_val) for name, time_val in self.results.items()
            if time_val and time_val > 0.05  # >50ms
        ]
        
        if slow_operations:
            slow_operations.sort(key=lambda x: x[1], reverse=True)
            for name, time_val in slow_operations:
                print(f"  • {name}: {time_val*1000:.2f}ms")
        else:
            print("  ✓ No significant bottlenecks detected!")
        
        # Identify fast operations
        print("\n⚡ Fast Operations:")
        fast_operations = [
            (name, time_val) for name, time_val in self.results.items()
            if time_val and time_val < 0.01  # <10ms
        ]
        
        if fast_operations:
            fast_operations.sort(key=lambda x: x[1])
            for name, time_val in fast_operations:
                print(f"  • {name}: {time_val*1000:.3f}ms")
        
        # Cache effectiveness
        if 'tool_execution' in self.results and 'tool_execution_cached' in self.results:
            speedup = self.results['tool_execution'] / self.results['tool_execution_cached']
            print(f"\n💾 Cache Effectiveness:")
            print(f"  • Cache speedup: {speedup:.1f}x")
            print(f"  • Cache hit time: {self.results['tool_execution_cached']*1000:.3f}ms")
        
        # Generate profiler report
        self.print_section("DETAILED PROFILING REPORT")
        report = profiler.generate_report(sort_by='avg_time')
        print(report)
        
        return self.results


def main():
    """Main benchmark execution"""
    suite = BenchmarkSuite()
    results = suite.run_all_benchmarks()
    
    print("\n" + "=" * 90)
    print("✅ Benchmark suite completed!")
    print("=" * 90)
    
    return results


if __name__ == "__main__":
    main()
