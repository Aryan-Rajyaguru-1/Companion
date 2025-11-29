#!/usr/bin/env python3
"""
Test Integrated Brain with All Phases
======================================

Tests that all phases (1-5) are properly integrated into brain.py
"""

import sys
import os

# Add paths
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
sys.path.insert(0, os.path.join(os.path.dirname(current_dir), 'website'))

from core.brain import CompanionBrain


def print_section(title: str):
    """Print section header"""
    print("\n" + "=" * 90)
    print(f"  {title}")
    print("=" * 90)


def test_brain_initialization():
    """Test brain initialization with all phases"""
    print_section("TEST 1: BRAIN INITIALIZATION")
    
    try:
        brain = CompanionBrain(
            app_type="general",
            enable_caching=True,
            enable_search=True,
            enable_learning=True
        )
        
        print(f"✅ Brain initialized successfully")
        print(f"   Session ID: {brain.session_id[:8]}")
        print(f"   App Type: {brain.app_type}")
        
        # Check which phases are available
        stats = brain.get_stats()
        phases = stats.get('phases_enabled', [])
        
        print(f"\n📦 Phases Enabled ({len(phases)}):")
        for phase in phases:
            print(f"   ✅ {phase}")
        
        if not phases or phases == ['Legacy components only']:
            print(f"   ⚠️  No new phases loaded (using legacy components)")
        
        return brain, True
        
    except Exception as e:
        print(f"❌ Brain initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return None, False


def test_phase4_code_execution(brain):
    """Test Phase 4: Code Execution"""
    print_section("TEST 2: PHASE 4 - CODE EXECUTION")
    
    if not brain.code_executor:
        print("⚠️  Phase 4 not available - skipping code execution test")
        return False
    
    try:
        # Test Python code
        python_code = """
def factorial(n):
    return 1 if n <= 1 else n * factorial(n-1)
print(f"Factorial of 5 is {factorial(5)}")
"""
        
        print("Testing Python code execution...")
        result = brain.execute_code(python_code, language='python')
        
        if result['success']:
            print(f"✅ Python execution successful")
            print(f"   Output: {result['output'].strip()}")
            print(f"   Time: {result['execution_time']:.4f}s")
        else:
            print(f"❌ Python execution failed: {result['error']}")
            return False
        
        # Test JavaScript code
        js_code = """
const sum = [1, 2, 3, 4, 5].reduce((a, b) => a + b, 0);
console.log('Sum:', sum);
"""
        
        print("\nTesting JavaScript code execution...")
        result = brain.execute_code(js_code, language='javascript')
        
        if result['success']:
            print(f"✅ JavaScript execution successful")
            print(f"   Output: {result['output'].strip()}")
            print(f"   Time: {result['execution_time']:.4f}s")
        else:
            print(f"❌ JavaScript execution failed: {result['error']}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Code execution test failed: {e}")
        return False


def test_phase4_tools(brain):
    """Test Phase 4: Tool Framework"""
    print_section("TEST 3: PHASE 4 - TOOL FRAMEWORK")
    
    if not brain.tool_executor:
        print("⚠️  Phase 4 not available - skipping tool test")
        return False
    
    try:
        # List available tools
        tools = brain.list_available_tools()
        print(f"✅ {len(tools)} tools available")
        
        # Show first 10 tools
        print("\nAvailable tools:")
        for tool in tools[:10]:
            print(f"   • {tool}")
        if len(tools) > 10:
            print(f"   ... and {len(tools) - 10} more")
        
        # Test math tools
        print("\nTesting math tools:")
        
        result = brain.call_tool('add', 10, 5)
        if result['success']:
            print(f"✅ add(10, 5) = {result['result']}")
        
        result = brain.call_tool('multiply', 7, 8)
        if result['success']:
            print(f"✅ multiply(7, 8) = {result['result']}")
        
        result = brain.call_tool('power', 2, 10)
        if result['success']:
            print(f"✅ power(2, 10) = {result['result']}")
        
        # Test text tools
        print("\nTesting text tools:")
        
        result = brain.call_tool('uppercase', 'hello world')
        if result['success']:
            print(f"✅ uppercase('hello world') = '{result['result']}'")
        
        result = brain.call_tool('count_words', 'The quick brown fox')
        if result['success']:
            print(f"✅ count_words('The quick brown fox') = {result['result']}")
        
        # Test caching
        print("\nTesting tool caching:")
        result1 = brain.call_tool('add', 100, 200, use_cache=True)
        cached1 = result1.get('cached', False)
        
        result2 = brain.call_tool('add', 100, 200, use_cache=True)
        cached2 = result2.get('cached', False)
        
        print(f"✅ First call: cached={cached1}")
        print(f"✅ Second call: cached={cached2}")
        
        if cached2:
            print("✅ Caching working correctly!")
        
        return True
        
    except Exception as e:
        print(f"❌ Tool test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_phase5_optimization(brain):
    """Test Phase 5: Optimization"""
    print_section("TEST 4: PHASE 5 - OPTIMIZATION")
    
    if not brain.profiler:
        print("⚠️  Phase 5 not available - skipping optimization test")
        return False
    
    try:
        # Get performance stats
        stats = brain.get_performance_stats()
        
        print("✅ Performance statistics available")
        
        if 'monitoring' in stats:
            monitoring = stats['monitoring']
            print(f"\nMonitoring:")
            print(f"   Memory: {monitoring.get('memory_mb', 'N/A')} MB")
            print(f"   CPU: {monitoring.get('cpu_percent', 'N/A')}%")
        
        if 'cache_stats' in stats:
            cache_stats = stats['cache_stats']
            print(f"\nCache Statistics:")
            print(f"   L1 Cache: {cache_stats['l1']}")
            print(f"   L2 Cache: {cache_stats['l2']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Optimization test failed: {e}")
        return False


def test_phase1_knowledge(brain):
    """Test Phase 1: Knowledge Layer"""
    print_section("TEST 5: PHASE 1 - KNOWLEDGE LAYER")
    
    if not brain.knowledge_retriever:
        print("⚠️  Phase 1 not available (requires Docker services)")
        return False
    
    try:
        # Test semantic search
        result = brain.semantic_search("Python programming", top_k=3)
        
        if result['success']:
            print(f"✅ Semantic search working")
            print(f"   Found {len(result['results'])} results")
        else:
            print(f"⚠️  Semantic search failed: {result['error']}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Knowledge layer test failed: {e}")
        return False


def test_phase2_search(brain):
    """Test Phase 2: Search Layer"""
    print_section("TEST 6: PHASE 2 - SEARCH LAYER")
    
    if not brain.search_engine:
        print("⚠️  Phase 2 not available (requires Docker services)")
        return False
    
    try:
        # Test hybrid search
        result = brain.hybrid_search("Python tutorial", limit=5)
        
        if result['success']:
            print(f"✅ Hybrid search working")
            print(f"   Found {len(result['results'])} results")
        else:
            print(f"⚠️  Hybrid search failed: {result['error']}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Search layer test failed: {e}")
        return False


def test_legacy_compatibility(brain):
    """Test that legacy components still work"""
    print_section("TEST 7: LEGACY COMPATIBILITY")
    
    try:
        # Test old think() method
        print("Testing legacy think() method...")
        
        response = brain.think(
            message="What is 2+2?",
            tools=[],
            user_id="test_user"
        )
        
        if response['success']:
            print(f"✅ Legacy think() method working")
            print(f"   Response: {response['response'][:100]}...")
        else:
            print(f"⚠️  Legacy method failed: {response.get('error')}")
            return False
        
        # Test conversation history
        history = brain.get_conversation_history(user_id="test_user")
        print(f"✅ Conversation history: {len(history)} messages")
        
        return True
        
    except Exception as e:
        print(f"❌ Legacy compatibility test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 90)
    print("  COMPANION BRAIN - INTEGRATED PHASES TEST SUITE")
    print("=" * 90)
    
    # Initialize brain
    brain, init_success = test_brain_initialization()
    
    if not init_success or not brain:
        print("\n❌ Brain initialization failed - cannot continue tests")
        return
    
    # Run tests
    results = {
        'Phase 4 - Code Execution': test_phase4_code_execution(brain),
        'Phase 4 - Tools': test_phase4_tools(brain),
        'Phase 5 - Optimization': test_phase5_optimization(brain),
        'Phase 1 - Knowledge': test_phase1_knowledge(brain),
        'Phase 2 - Search': test_phase2_search(brain),
        'Legacy Compatibility': test_legacy_compatibility(brain)
    }
    
    # Summary
    print_section("TEST SUMMARY")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\nResults: {passed}/{total} tests passed\n")
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {status}: {test_name}")
    
    # Final statistics
    print_section("FINAL STATISTICS")
    
    stats = brain.get_stats()
    print(f"\nBrain Statistics:")
    print(f"  Total Requests: {stats['total_requests']}")
    print(f"  Successful: {stats['successful_requests']}")
    print(f"  Failed: {stats['failed_requests']}")
    print(f"  Success Rate: {stats['success_rate']:.1f}%")
    print(f"  Active Conversations: {stats['active_conversations']}")
    
    phases = stats.get('phases_enabled', [])
    print(f"\n  Phases Enabled: {len(phases)}")
    for phase in phases:
        print(f"    • {phase}")
    
    print("\n" + "=" * 90)
    
    if passed == total:
        print("✅ ALL TESTS PASSED - Brain fully operational!")
    elif passed > 0:
        print(f"⚠️  PARTIAL SUCCESS - {passed}/{total} tests passed")
    else:
        print("❌ ALL TESTS FAILED")
    
    print("=" * 90)


if __name__ == "__main__":
    main()
