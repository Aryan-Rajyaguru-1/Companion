#!/usr/bin/env python3
"""
Unified Brain Demo - All Phases Integration
============================================

This demo showcases the complete integrated brain with ALL phases:
- Phase 1: Knowledge retrieval
- Phase 2: Hybrid search  
- Phase 3: Web intelligence
- Phase 4: Code execution & tools
- Phase 5: Optimization

Run: python unified_brain_demo.py
"""

import sys
import os

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from core.unified_brain import create_brain
import time
import json


def print_section(title):
    """Print formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_result(result, title="Result"):
    """Print formatted result"""
    print(f"\n{title}:")
    print("-" * 60)
    if isinstance(result, dict):
        print(json.dumps(result, indent=2, default=str))
    else:
        print(result)
    print("-" * 60)


def demo_basic_thinking():
    """Demo 1: Basic thinking capability"""
    print_section("DEMO 1: Basic Thinking")
    
    brain = create_brain(app_type="general")
    
    queries = [
        "What is artificial intelligence?",
        "Explain quantum computing in simple terms",
        "How does machine learning work?"
    ]
    
    for query in queries:
        print(f"🤔 Query: {query}")
        result = brain.think(query)
        print(f"✅ Response: {result['response'][:200]}...")
        print(f"⏱️  Time: {result['metadata']['response_time']:.3f}s")
        print()


def demo_knowledge_retrieval():
    """Demo 2: Knowledge-enhanced responses"""
    print_section("DEMO 2: Knowledge Retrieval (Phase 1)")
    
    brain = create_brain(app_type="research")
    
    # First without knowledge
    print("Without knowledge base:")
    result = brain.think("What is RAG?", use_knowledge=False)
    print(f"Response: {result['response'][:200]}...")
    
    # Then with knowledge
    print("\nWith knowledge base:")
    result = brain.think("What is RAG?", use_knowledge=True)
    print(f"Response: {result['response'][:200]}...")
    print(f"Used knowledge: {result['metadata'].get('used_knowledge', False)}")


def demo_search_capabilities():
    """Demo 3: Hybrid search"""
    print_section("DEMO 3: Hybrid Search (Phase 2)")
    
    brain = create_brain()
    
    # Hybrid search
    print("Performing hybrid search...")
    result = brain.hybrid_search("machine learning algorithms", limit=5)
    
    if result['success']:
        print(f"✅ Found {result['count']} results")
        if result.get('results'):
            print("\nTop results:")
            for i, hit in enumerate(result['results'].get('hits', [])[:3], 1):
                print(f"  {i}. {hit.get('title', 'N/A')}")
    else:
        print(f"⚠️  Search not available: {result.get('error')}")


def demo_web_intelligence():
    """Demo 4: Web intelligence"""
    print_section("DEMO 4: Web Intelligence (Phase 3)")
    
    brain = create_brain()
    
    # Search web
    print("1. Web Search:")
    result = brain.search_web("Python tutorials 2024", limit=3)
    print_result(result, "Web Search Result")
    
    # Get news
    print("\n2. News Search:")
    result = brain.get_news("artificial intelligence", limit=3)
    print_result(result, "News Result")
    
    # Scrape URL (example)
    print("\n3. Web Scraping:")
    result = brain.scrape_web("https://python.org")
    if result['success']:
        print(f"✅ Scraped {len(result.get('content', ''))} characters")
    else:
        print(f"⚠️  Scraping: {result.get('error')}")


def demo_code_execution():
    """Demo 5: Code execution"""
    print_section("DEMO 5: Code Execution (Phase 4)")
    
    brain = create_brain(app_type="coder")
    
    # Python execution
    print("1. Python Code Execution:")
    result = brain.execute_code("""
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

print("Fibonacci sequence:")
for i in range(10):
    print(f"F({i}) = {fibonacci(i)}")
""", language="python")
    
    print_result(result, "Python Execution")
    
    # JavaScript execution
    print("\n2. JavaScript Code Execution:")
    result = brain.execute_code("""
function isPrime(n) {
    if (n <= 1) return false;
    for (let i = 2; i <= Math.sqrt(n); i++) {
        if (n % i === 0) return false;
    }
    return true;
}

console.log("Prime numbers up to 50:");
for (let i = 2; i <= 50; i++) {
    if (isPrime(i)) process.stdout.write(i + " ");
}
console.log();
""", language="javascript")
    
    print_result(result, "JavaScript Execution")


def demo_tool_calling():
    """Demo 6: Tool calling framework"""
    print_section("DEMO 6: Tool Calling (Phase 4)")
    
    brain = create_brain()
    
    # List available tools
    print("Available tools:")
    tools = brain.list_tools()
    print(f"Total: {len(tools)} tools")
    for tool in tools[:10]:  # Show first 10
        print(f"  • {tool}")
    
    # Call some tools
    print("\n\nCalling tools:")
    
    # Math tools
    print("\n1. Add:")
    result = brain.call_tool("add", 42, 58)
    print(f"Result: {result}")
    
    print("\n2. Multiply:")
    result = brain.call_tool("multiply", 12, 8)
    print(f"Result: {result}")
    
    # String tools
    print("\n3. Reverse String:")
    result = brain.call_tool("reverse_string", "Hello Companion!")
    print(f"Result: {result}")
    
    # Search tools
    print("\n4. Search Tools:")
    matching = brain.search_tools("string")
    print(f"Tools matching 'string': {matching}")


def demo_optimization():
    """Demo 7: Performance optimization"""
    print_section("DEMO 7: Optimization (Phase 5)")
    
    brain = create_brain()
    
    # Test caching
    print("Testing cache performance...")
    
    query = "What is Python?"
    
    # First call (uncached)
    start = time.time()
    result1 = brain.think(query)
    time1 = time.time() - start
    print(f"First call:  {time1:.4f}s")
    
    # Second call (cached)
    start = time.time()
    result2 = brain.think(query)
    time2 = time.time() - start
    print(f"Second call: {time2:.4f}s (cached)")
    
    speedup = time1 / time2 if time2 > 0 else float('inf')
    print(f"Speedup: {speedup:.1f}x")
    
    # Performance stats
    print("\n\nPerformance Statistics:")
    stats = brain.get_performance_stats()
    print_result(stats, "Stats")
    
    # Health check
    print("\n\nHealth Status:")
    health = brain.get_health()
    print_result(health, "Health")


def demo_conversation_management():
    """Demo 8: Conversation context"""
    print_section("DEMO 8: Conversation Management")
    
    brain = create_brain()
    
    user_id = "user123"
    
    # Multi-turn conversation
    print("Starting conversation...")
    
    brain.think("My name is Alice", user_id=user_id)
    print("User: My name is Alice")
    
    brain.think("I love programming in Python", user_id=user_id)
    print("User: I love programming in Python")
    
    result = brain.think("What's my name and what do I like?", user_id=user_id)
    print(f"User: What's my name and what do I like?")
    print(f"Brain: {result['response'][:200]}...")
    
    # Get history
    print("\n\nConversation History:")
    history = brain.get_conversation_history(user_id=user_id)
    print(f"Total messages: {len(history)}")
    for msg in history[-4:]:  # Show last 4
        print(f"  {msg['role']}: {msg['content'][:80]}...")


def demo_full_integration():
    """Demo 9: All phases together"""
    print_section("DEMO 9: Full Integration - All Phases")
    
    brain = create_brain(app_type="research")
    
    print("Query: 'Write Python code to calculate factorial, then execute it'")
    print()
    
    # 1. Think about the request
    result = brain.think(
        "Write Python code to calculate factorial",
        use_knowledge=True,
        use_search=False
    )
    print(f"1. Generated response: {result['response'][:200]}...")
    
    # 2. Execute the code
    code = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

for i in range(1, 11):
    print(f"{i}! = {factorial(i)}")
"""
    
    print("\n2. Executing code...")
    exec_result = brain.execute_code(code, language="python")
    
    if exec_result['success']:
        print("✅ Execution successful!")
        print(f"Output:\n{exec_result['output']}")
    else:
        print(f"❌ Execution failed: {exec_result.get('error')}")
    
    # 3. Show performance
    print("\n3. Performance:")
    stats = brain.get_performance_stats()
    print(f"Total requests: {stats['total_requests']}")
    print(f"Success rate: {stats['successful_requests']}/{stats['total_requests']}")
    print(f"Phase usage: {stats['phase_usage']}")


def main():
    """Run all demos"""
    print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║                   UNIFIED COMPANION BRAIN DEMO                            ║
║                                                                           ║
║  Showcasing integration of ALL 5 phases:                                 ║
║  ✓ Phase 1: Knowledge Layer                                              ║
║  ✓ Phase 2: Search Layer                                                 ║
║  ✓ Phase 3: Web Intelligence                                             ║
║  ✓ Phase 4: Execution & Generation                                       ║
║  ✓ Phase 5: Optimization                                                 ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
""")
    
    demos = [
        ("Basic Thinking", demo_basic_thinking),
        ("Knowledge Retrieval", demo_knowledge_retrieval),
        ("Search Capabilities", demo_search_capabilities),
        ("Web Intelligence", demo_web_intelligence),
        ("Code Execution", demo_code_execution),
        ("Tool Calling", demo_tool_calling),
        ("Optimization", demo_optimization),
        ("Conversation Management", demo_conversation_management),
        ("Full Integration", demo_full_integration),
    ]
    
    for name, demo_func in demos:
        try:
            demo_func()
        except Exception as e:
            print(f"\n❌ Demo '{name}' error: {e}")
            import traceback
            traceback.print_exc()
        
        input("\n\n[Press Enter to continue to next demo...]")
    
    print_section("DEMO COMPLETE")
    print("✅ All demos finished!")
    print("\nYou now have a fully integrated brain with ALL phase capabilities!")


if __name__ == "__main__":
    main()
