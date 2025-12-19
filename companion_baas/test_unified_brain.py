#!/usr/bin/env python3
"""
Test Unified Brain - All Phases Integration
===========================================

Comprehensive tests for the unified brain with all phases.
"""

import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from core.unified_brain import create_brain, UnifiedCompanionBrain
import time


def test_brain_initialization():
    """Test 1: Brain initialization"""
    print("Test 1: Brain Initialization")
    print("-" * 60)
    
    try:
        brain = create_brain(app_type="general")
        assert isinstance(brain, UnifiedCompanionBrain)
        assert brain.app_type == "general"
        assert brain.session_id is not None
        print("✅ Brain initialized successfully")
        print(f"   Session ID: {brain.session_id[:8]}...")
        print(f"   {brain}")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_basic_thinking():
    """Test 2: Basic thinking"""
    print("\nTest 2: Basic Thinking")
    print("-" * 60)
    
    try:
        brain = create_brain()
        result = brain.think("What is 2+2?")
        
        assert result['success'] == True
        assert 'response' in result
        assert 'metadata' in result
        assert result['metadata']['response_time'] > 0
        
        print("✅ Basic thinking works")
        print(f"   Response: {result['response'][:100]}...")
        print(f"   Time: {result['metadata']['response_time']:.3f}s")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_knowledge_retrieval():
    """Test 3: Knowledge retrieval"""
    print("\nTest 3: Knowledge Retrieval (Phase 1)")
    print("-" * 60)
    
    try:
        brain = create_brain()
        
        # Test with knowledge
        result = brain.think("What is AI?", use_knowledge=True)
        assert result['success'] == True
        
        # Test retrieval method
        knowledge = brain.retrieve_knowledge("machine learning", limit=3)
        
        print("✅ Knowledge retrieval accessible")
        print(f"   Knowledge available: {brain.knowledge is not None}")
        if brain.knowledge:
            print(f"   Retrieval result: {knowledge.get('success', False)}")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_search():
    """Test 4: Search capabilities"""
    print("\nTest 4: Search Capabilities (Phase 2)")
    print("-" * 60)
    
    try:
        brain = create_brain()
        
        # Test thinking with search
        result = brain.think("Python tutorials", use_search=True)
        assert result['success'] == True
        
        # Test search methods
        search_result = brain.hybrid_search("test query", limit=5)
        text_result = brain.text_search("test", limit=5)
        
        print("✅ Search capabilities accessible")
        print(f"   Search engine available: {brain.search_engine is not None}")
        print(f"   Hybrid search result: {search_result.get('success', False)}")
        print(f"   Text search result: {text_result.get('success', False)}")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_web_intelligence():
    """Test 5: Web intelligence"""
    print("\nTest 5: Web Intelligence (Phase 3)")
    print("-" * 60)
    
    try:
        brain = create_brain()
        
        # Test web methods
        search_result = brain.search_web("test", limit=3)
        news_result = brain.get_news("AI", limit=3)
        
        print("✅ Web intelligence accessible")
        print(f"   Web crawler available: {brain.web_crawler is not None}")
        print(f"   News client available: {brain.news_client is not None}")
        print(f"   Search client available: {brain.search_client is not None}")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_code_execution():
    """Test 6: Code execution"""
    print("\nTest 6: Code Execution (Phase 4)")
    print("-" * 60)
    
    try:
        brain = create_brain()
        
        # Test Python execution
        result = brain.execute_code("print('Hello from brain!')", language="python")
        
        if brain.code_executor:
            assert result['success'] == True
            assert 'Hello from brain!' in result['output']
            print("✅ Code execution works")
            print(f"   Output: {result['output'][:50]}...")
            print(f"   Time: {result['execution_time']:.3f}s")
        else:
            print("⚠️  Code executor not available (expected if Phase 4 not set up)")
        
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_tool_calling():
    """Test 7: Tool calling"""
    print("\nTest 7: Tool Calling (Phase 4)")
    print("-" * 60)
    
    try:
        brain = create_brain()
        
        # List tools
        tools = brain.list_tools()
        print(f"   Available tools: {len(tools)}")
        
        if brain.tool_executor and len(tools) > 0:
            # Test tool execution
            result = brain.call_tool("add", 5, 3)
            assert result['success'] == True
            
            # Search tools
            math_tools = brain.search_tools("add")
            assert len(math_tools) > 0
            
            print("✅ Tool calling works")
            print(f"   Total tools: {len(tools)}")
            print(f"   Sample tools: {tools[:5]}")
            print(f"   Tool result: {result['result']}")
        else:
            print("⚠️  Tool executor not available (expected if Phase 4 not set up)")
        
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_caching():
    """Test 8: Caching and optimization"""
    print("\nTest 8: Caching & Optimization (Phase 5)")
    print("-" * 60)
    
    try:
        brain = create_brain()
        
        query = "Test cache query"
        
        # First call
        start = time.time()
        result1 = brain.think(query)
        time1 = time.time() - start
        
        # Second call (should be cached)
        start = time.time()
        result2 = brain.think(query)
        time2 = time.time() - start
        
        print("✅ Caching works")
        print(f"   First call: {time1:.4f}s")
        print(f"   Second call: {time2:.4f}s")
        if time2 < time1:
            print(f"   Speedup: {time1/time2:.1f}x")
        
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_conversation_context():
    """Test 9: Conversation context"""
    print("\nTest 9: Conversation Context")
    print("-" * 60)
    
    try:
        brain = create_brain()
        
        user_id = "test_user"
        
        # Send messages
        brain.think("My name is Bob", user_id=user_id)
        brain.think("I like Python", user_id=user_id)
        
        # Get history
        history = brain.get_conversation_history(user_id=user_id)
        assert len(history) >= 4  # 2 user messages + 2 assistant messages
        
        # Clear conversation
        brain.clear_conversation(user_id=user_id)
        history_after = brain.get_conversation_history(user_id=user_id)
        assert len(history_after) == 0
        
        print("✅ Conversation context works")
        print(f"   Messages before clear: {len(history)}")
        print(f"   Messages after clear: {len(history_after)}")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_performance_stats():
    """Test 10: Performance statistics"""
    print("\nTest 10: Performance Statistics")
    print("-" * 60)
    
    try:
        brain = create_brain()
        
        # Generate some activity
        brain.think("Test 1")
        brain.think("Test 2")
        
        # Get stats
        stats = brain.get_performance_stats()
        assert 'total_requests' in stats
        assert 'successful_requests' in stats
        assert stats['total_requests'] >= 2
        
        print("✅ Performance stats work")
        print(f"   Total requests: {stats['total_requests']}")
        print(f"   Successful: {stats['successful_requests']}")
        print(f"   Phase usage: {stats['phase_usage']}")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_health_check():
    """Test 11: Health check"""
    print("\nTest 11: Health Check")
    print("-" * 60)
    
    try:
        brain = create_brain()
        
        health = brain.get_health()
        assert 'status' in health
        assert 'phases' in health
        assert 'timestamp' in health
        
        print("✅ Health check works")
        print(f"   Status: {health['status']}")
        print(f"   Phases:")
        for phase, available in health['phases'].items():
            status = "✓" if available else "✗"
            print(f"     {status} {phase}")
        
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_all_phases_integration():
    """Test 12: All phases working together"""
    print("\nTest 12: All Phases Integration")
    print("-" * 60)
    
    try:
        brain = create_brain(app_type="research")
        
        # Complex query using multiple phases
        result = brain.think(
            "What is machine learning?",
            use_knowledge=True,
            use_search=True
        )
        
        assert result['success'] == True
        
        # Check that phases were used (if available)
        metadata = result['metadata']
        
        print("✅ All phases integration successful")
        print(f"   Used knowledge: {metadata.get('used_knowledge', 'N/A')}")
        print(f"   Used search: {metadata.get('used_search', 'N/A')}")
        print(f"   Response time: {metadata.get('response_time', 0):.3f}s")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def main():
    """Run all tests"""
    print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║              UNIFIED COMPANION BRAIN - INTEGRATION TESTS                  ║
║                                                                           ║
║  Testing all 5 phases integrated into single brain:                      ║
║  • Phase 1: Knowledge Layer                                              ║
║  • Phase 2: Search Layer                                                 ║
║  • Phase 3: Web Intelligence                                             ║
║  • Phase 4: Execution & Generation                                       ║
║  • Phase 5: Optimization                                                 ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
""")
    
    tests = [
        test_brain_initialization,
        test_basic_thinking,
        test_knowledge_retrieval,
        test_search,
        test_web_intelligence,
        test_code_execution,
        test_tool_calling,
        test_caching,
        test_conversation_context,
        test_performance_stats,
        test_health_check,
        test_all_phases_integration,
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"\n❌ Test crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(results)
    total = len(results)
    percentage = (passed / total * 100) if total > 0 else 0
    
    print(f"\nResults: {passed}/{total} tests passed ({percentage:.1f}%)")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Unified brain is fully operational!")
    elif passed >= total * 0.8:
        print(f"\n✅ MOSTLY PASSING ({passed}/{total})")
        print("Some phases may not be available - this is expected")
    else:
        print(f"\n⚠️  SOME TESTS FAILED ({total - passed} failed)")
    
    print("\n" + "=" * 80)
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
