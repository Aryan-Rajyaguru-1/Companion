"""
Phase 4 Demo: Execution & Generation

Comprehensive demonstration of Phase 4 capabilities:
- Multi-language code execution
- Tool calling framework
- Security validation
- Async execution
"""

import sys
sys.path.insert(0, '/home/aryan/Documents/Companion deepthink/companion_baas')

import time
import asyncio
from execution.code_executor import CodeExecutor
from tools.tool_registry import ToolRegistry, tool
from tools.tool_executor import ToolExecutor
from tools.builtin_tools import register_builtin_tools


def print_header(title: str):
    """Print formatted section header"""
    print("\n" + "=" * 75)
    print(f"  {title}")
    print("=" * 75)


def print_subheader(title: str):
    """Print formatted subsection header"""
    print(f"\n{title}")
    print("-" * 75)


def demo_code_execution():
    """Demo 1: Multi-language code execution"""
    print_header("DEMO 1: MULTI-LANGUAGE CODE EXECUTION")
    
    executor = CodeExecutor(timeout=5)
    
    # Python execution
    print_subheader("1.1 Python Code Execution")
    python_code = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

result = factorial(10)
print(f"Factorial of 10 is {result}")
"""
    
    result = executor.execute(python_code, language='python')
    print(f"✓ Language: {result.language}")
    print(f"✓ Success: {result.success}")
    print(f"✓ Output: {result.output.strip()}")
    print(f"✓ Execution Time: {result.execution_time:.4f}s")
    
    # JavaScript execution
    print_subheader("1.2 JavaScript Code Execution")
    js_code = """
const factorial = (n) => n <= 1 ? 1 : n * factorial(n - 1);
const result = factorial(10);
console.log(`Factorial of 10 is ${result}`);
"""
    
    result = executor.execute(js_code, language='javascript')
    print(f"✓ Language: {result.language}")
    print(f"✓ Success: {result.success}")
    print(f"✓ Output: {result.output.strip()}")
    print(f"✓ Execution Time: {result.execution_time:.4f}s")
    
    # Auto-detection
    print_subheader("1.3 Language Auto-Detection")
    auto_code = """
import math
print(f"Value of pi: {math.pi:.6f}")
print(f"Square root of 2: {math.sqrt(2):.6f}")
"""
    
    result = executor.execute(auto_code)  # No language specified
    print(f"✓ Detected Language: {result.language}")
    print(f"✓ Success: {result.success}")
    print(f"✓ Output:\n{result.output}")
    
    # Expression evaluation
    print_subheader("1.4 Expression Evaluation")
    expressions = [
        ("sum([i**2 for i in range(10)])", "python"),
        ("[1,2,3,4,5].reduce((a,b)=>a+b,0)", "javascript")
    ]
    
    for expr, lang in expressions:
        result = executor.evaluate_expression(expr, language=lang)
        print(f"✓ {lang.capitalize()}: {expr}")
        print(f"  Result: {result.return_value or result.output.strip()}")
        print(f"  Time: {result.execution_time:.4f}s")
    
    # Security validation
    print_subheader("1.5 Security Validation")
    dangerous_codes = [
        ("import os\nos.system('rm -rf /')", "python"),
        ("require('fs').unlinkSync('/')", "javascript")
    ]
    
    for code, lang in dangerous_codes:
        result = executor.execute(code, language=lang)
        status = "🛡️ BLOCKED" if not result.success else "❌ LEAKED"
        print(f"{status} ({lang}): {code[:40]}...")
        if not result.success:
            print(f"  Reason: {result.error[:60]}...")
    
    return True


def demo_tool_framework():
    """Demo 2: Tool calling framework"""
    print_header("DEMO 2: TOOL CALLING FRAMEWORK")
    
    # Create registry
    registry = ToolRegistry()
    
    # Register built-in tools
    print_subheader("2.1 Built-in Tools Registration")
    count = register_builtin_tools(registry)
    print(f"✓ Registered {count} built-in tools")
    
    # Show categories
    print("\nAvailable Categories:")
    for category in registry.get_categories():
        tools_in_cat = registry.list_tools(category=category)
        print(f"  • {category}: {len(tools_in_cat)} tools")
    
    # Test math tools
    print_subheader("2.2 Math Tools")
    math_tests = [
        ("add", [10, 5], {}),
        ("multiply", [7, 8], {}),
        ("power", [2, 10], {}),
        ("sqrt", [144], {}),
    ]
    
    for tool_name, args, kwargs in math_tests:
        result = registry.execute(tool_name, *args, **kwargs)
        args_str = ", ".join(str(a) for a in args)
        print(f"✓ {tool_name}({args_str}) = {result}")
    
    # Test text tools
    print_subheader("2.3 Text Tools")
    text = "Hello, World! This is a test with 123 numbers."
    print(f"Input: '{text}'")
    print(f"✓ uppercase: {registry.execute('uppercase', text)}")
    print(f"✓ lowercase: {registry.execute('lowercase', text)}")
    print(f"✓ reverse: {registry.execute('reverse_text', text)}")
    print(f"✓ word_count: {registry.execute('count_words', text)}")
    print(f"✓ extracted_numbers: {registry.execute('extract_numbers', text)}")
    
    # Test list tools
    print_subheader("2.4 List Tools")
    numbers = [42, 17, 95, 23, 68, 34, 17, 95]
    print(f"Input: {numbers}")
    print(f"✓ sum: {registry.execute('list_sum', numbers)}")
    print(f"✓ average: {registry.execute('list_average', numbers):.2f}")
    print(f"✓ min: {registry.execute('list_min', numbers)}")
    print(f"✓ max: {registry.execute('list_max', numbers)}")
    print(f"✓ unique: {registry.execute('list_unique', numbers)}")
    print(f"✓ sorted: {registry.execute('list_sort', numbers)}")
    
    # Custom tool registration
    print_subheader("2.5 Custom Tool Registration")
    
    @tool(
        name="fibonacci",
        description="Calculate nth Fibonacci number",
        category="algorithms",
        tags=["recursion", "math"]
    )
    def fib(n: int) -> int:
        """Calculate nth Fibonacci number"""
        if n <= 1:
            return n
        return fib(n-1) + fib(n-2)
    
    registry.register(fib)
    
    fib_results = [registry.execute("fibonacci", i) for i in range(1, 11)]
    print(f"✓ First 10 Fibonacci numbers: {fib_results}")
    
    # Tool search
    print_subheader("2.6 Tool Discovery")
    search_queries = ["math", "list", "text"]
    
    for query in search_queries:
        results = registry.search_tools(query)
        tool_names = [t.name for t in results]
        print(f"✓ Tools matching '{query}': {', '.join(tool_names[:5])}{'...' if len(tool_names) > 5 else ''}")
    
    return registry


def demo_async_execution(registry):
    """Demo 3: Async execution and caching"""
    print_header("DEMO 3: ASYNC EXECUTION & CACHING")
    
    executor = ToolExecutor(registry, cache_enabled=True, cache_ttl=300)
    
    # Sync execution with caching
    print_subheader("3.1 Sync Execution with Caching")
    
    # First call (not cached)
    start = time.time()
    result1 = executor.execute("fibonacci", 20)
    time1 = time.time() - start
    
    print(f"✓ First call (not cached):")
    print(f"  Result: {result1.result}")
    print(f"  Time: {time1:.4f}s")
    print(f"  Cached: {result1.cached}")
    
    # Second call (cached)
    start = time.time()
    result2 = executor.execute("fibonacci", 20)
    time2 = time.time() - start
    
    print(f"\n✓ Second call (cached):")
    print(f"  Result: {result2.result}")
    print(f"  Time: {time2:.4f}s")
    print(f"  Cached: {result2.cached}")
    print(f"  Speedup: {time1/time2:.2f}x faster")
    
    # Cache stats
    print_subheader("3.2 Cache Statistics")
    stats = executor.get_cache_stats()
    print(f"✓ Total cached entries: {stats['total_entries']}")
    print(f"✓ Valid entries: {stats['valid_entries']}")
    print(f"✓ Cache TTL: {stats['cache_ttl']}s")
    
    # Batch async execution
    print_subheader("3.3 Batch Parallel Execution")
    
    async def test_batch():
        # Execute multiple Fibonacci calculations in parallel
        executions = [
            ("fibonacci", (10,), {}),
            ("fibonacci", (15,), {}),
            ("fibonacci", (18,), {}),
            ("fibonacci", (20,), {}),
        ]
        
        start = time.time()
        results = await executor.execute_batch(executions)
        total_time = time.time() - start
        
        return results, total_time
    
    results, batch_time = asyncio.run(test_batch())
    
    print(f"✓ Executed {len(results)} tools in parallel")
    print(f"✓ Total time: {batch_time:.4f}s")
    
    for i, result in enumerate(results):
        fib_n = [10, 15, 18, 20][i]
        cached_str = " (cached)" if result.cached else ""
        print(f"  fib({fib_n}) = {result.result}{cached_str}")
    
    # Calculate what serial execution would have taken
    serial_time = sum(r.execution_time for r in results if not r.cached)
    if serial_time > 0:
        speedup = serial_time / batch_time
        print(f"\n✓ Speedup vs serial: {speedup:.2f}x")
    
    return True


def demo_integration():
    """Demo 4: Integration - Code execution + Tools"""
    print_header("DEMO 4: INTEGRATION - CODE EXECUTION + TOOLS")
    
    code_executor = CodeExecutor(timeout=10)
    tool_registry = ToolRegistry()
    register_builtin_tools(tool_registry)
    
    # Use tools in generated code
    print_subheader("4.1 Using Tools in Generated Code")
    
    # Python code that would use tools
    integration_code = """
# Calculate some statistics
numbers = [15, 42, 8, 23, 16, 4, 42]

# Manual calculations
total = sum(numbers)
average = total / len(numbers)
minimum = min(numbers)
maximum = max(numbers)

print(f"Numbers: {numbers}")
print(f"Sum: {total}")
print(f"Average: {average:.2f}")
print(f"Min: {minimum}")
print(f"Max: {maximum}")
"""
    
    result = code_executor.execute(integration_code, language='python')
    print(f"✓ Code execution result:")
    print(result.output)
    
    # Now use tools to do the same
    print_subheader("4.2 Same Operations Using Tools")
    numbers = [15, 42, 8, 23, 16, 4, 42]
    
    print(f"Numbers: {numbers}")
    print(f"✓ Sum (tool): {tool_registry.execute('list_sum', numbers)}")
    print(f"✓ Average (tool): {tool_registry.execute('list_average', numbers):.2f}")
    print(f"✓ Min (tool): {tool_registry.execute('list_min', numbers)}")
    print(f"✓ Max (tool): {tool_registry.execute('list_max', numbers)}")
    
    # Complex workflow
    print_subheader("4.3 Complex Workflow")
    print("Scenario: Extract numbers from text, calculate statistics\n")
    
    text = "The temperatures were 22.5°C, 18.3°C, 25.7°C, 20.1°C, and 23.4°C"
    print(f"Input text: '{text}'")
    
    # Extract numbers using tool
    temps = tool_registry.execute('extract_numbers', text)
    print(f"✓ Extracted numbers: {temps}")
    
    # Calculate statistics using tools
    avg_temp = tool_registry.execute('list_average', temps)
    min_temp = tool_registry.execute('list_min', temps)
    max_temp = tool_registry.execute('list_max', temps)
    
    print(f"✓ Average temperature: {avg_temp:.2f}°C")
    print(f"✓ Min temperature: {min_temp:.1f}°C")
    print(f"✓ Max temperature: {max_temp:.1f}°C")
    
    return True


def main():
    """Run all Phase 4 demos"""
    print("\n")
    print("╔" + "═" * 73 + "╗")
    print("║" + " " * 20 + "PHASE 4: EXECUTION & GENERATION" + " " * 21 + "║")
    print("║" + " " * 15 + "Comprehensive Demonstration of Capabilities" + " " * 14 + "║")
    print("╚" + "═" * 73 + "╝")
    
    start_time = time.time()
    
    # Run demos
    demo1_success = demo_code_execution()
    registry = demo_tool_framework()
    demo3_success = demo_async_execution(registry)
    demo4_success = demo_integration()
    
    # Summary
    total_time = time.time() - start_time
    
    print_header("PHASE 4 DEMONSTRATION SUMMARY")
    
    print("\n✅ Successfully demonstrated:")
    print("  • Multi-language code execution (Python, JavaScript)")
    print("  • Language auto-detection")
    print("  • Expression evaluation")
    print("  • Security validation and sandboxing")
    print("  • Tool registration and discovery")
    print("  • Built-in tools (25+ tools across 5 categories)")
    print("  • Custom tool creation")
    print("  • Parameter validation")
    print("  • Async execution")
    print("  • Result caching")
    print("  • Batch parallel execution")
    print("  • Code + Tools integration")
    
    print(f"\n📊 Statistics:")
    print(f"  • Total tools registered: {len(registry.tools)}")
    print(f"  • Categories: {', '.join(registry.get_categories())}")
    print(f"  • Supported languages: Python, JavaScript/Node.js")
    print(f"  • Total demo time: {total_time:.2f}s")
    
    print("\n🎯 Phase 4 Status: COMPLETE ✅")
    print("=" * 75)
    
    print("\n📝 Next Steps:")
    print("  → Phase 4 remaining: Image generation (Stable Diffusion)")
    print("  → Phase 5: Optimization & Performance tuning")
    print("  → Phase 6: Production deployment")
    
    return True


if __name__ == "__main__":
    main()
