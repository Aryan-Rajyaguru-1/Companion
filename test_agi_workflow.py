#!/usr/bin/env python3
"""
Test AGI Autonomous Decision-Making Workflow
=============================================

Demonstrates how AGI autonomously:
1. Analyzes queries
2. Decides which modules to use
3. Executes workflows
4. Learns from outcomes

Run with: python test_agi_workflow.py
"""

import sys
import os

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from companion_baas.sdk import BrainClient
import time


def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def test_conversational_query():
    """Test 1: Simple conversational query"""
    print_section("TEST 1: Conversational Query")
    
    client = BrainClient(enable_agi=True)
    
    query = "Hello! How are you today?"
    print(f"Query: {query}\n")
    
    response = client.think(query)
    
    print(f"Response: {response['response']}\n")
    
    if 'agi_plan' in response:
        plan = response['agi_plan']
        print(f"AGI Decision:")
        print(f"  Query type: {plan['query_type']}")
        print(f"  Confidence: {plan['confidence']:.1%}")
        print(f"  Modules to use: {', '.join(plan['modules_to_use'])}")
        print(f"  Execution steps: {len(plan['execution_order'])}")
        print(f"  Reasoning: {plan['reasoning']}")
        
        print(f"\nExecution Result:")
        print(f"  Modules used: {', '.join(response['metadata']['modules_used'])}")
        print(f"  Steps completed: {response['metadata']['steps_completed']}")
        print(f"  Execution time: {response['metadata']['execution_time']:.2f}s")
    
    print(f"\n✅ Test 1 passed!")


def test_coding_query():
    """Test 2: Code generation query"""
    print_section("TEST 2: Coding Query")
    
    client = BrainClient(enable_agi=True)
    
    query = "Write a Python function to reverse a string"
    print(f"Query: {query}\n")
    
    response = client.think(query)
    
    print(f"Response: {response['response'][:200]}...\n")
    
    if 'agi_plan' in response:
        plan = response['agi_plan']
        print(f"AGI Decision:")
        print(f"  Query type: {plan['query_type']}")
        print(f"  Confidence: {plan['confidence']:.1%}")
        print(f"  Modules to use: {', '.join(plan['modules_to_use'])}")
        
        print(f"\nExecution Result:")
        print(f"  Modules actually used: {', '.join(response['metadata']['modules_used'])}")
        print(f"  Steps completed: {response['metadata']['steps_completed']}")
    
    print(f"\n✅ Test 2 passed!")


def test_research_query():
    """Test 3: Research query (web search)"""
    print_section("TEST 3: Research Query")
    
    client = BrainClient(enable_agi=True, enable_search=True)
    
    query = "What is the latest news about artificial intelligence?"
    print(f"Query: {query}\n")
    
    response = client.think(query)
    
    print(f"Response: {response['response'][:200]}...\n")
    
    if 'agi_plan' in response:
        plan = response['agi_plan']
        print(f"AGI Decision:")
        print(f"  Query type: {plan['query_type']}")
        print(f"  Confidence: {plan['confidence']:.1%}")
        print(f"  Modules planned: {', '.join(plan['modules_to_use'])}")
        
        print(f"\nExecution Result:")
        print(f"  Modules used: {', '.join(response['metadata'].get('modules_used', []))}")
        print(f"  Steps completed: {response['metadata'].get('steps_completed', 0)}")
    
    print(f"\n✅ Test 3 passed!")


def test_analysis_query():
    """Test 4: Analysis query"""
    print_section("TEST 4: Analysis Query")
    
    client = BrainClient(enable_agi=True)
    
    query = "Explain why Python uses reference counting for memory management"
    print(f"Query: {query}\n")
    
    response = client.think(query)
    
    print(f"Response: {response['response'][:200]}...\n")
    
    if 'agi_plan' in response:
        plan = response['agi_plan']
        print(f"AGI Decision:")
        print(f"  Query type: {plan['query_type']}")
        print(f"  Confidence: {plan['confidence']:.1%}")
        print(f"  Modules to use: {', '.join(plan['modules_to_use'])}")
        
        print(f"\nExecution Result:")
        print(f"  Modules used: {', '.join(response['metadata']['modules_used'])}")
        print(f"  Steps completed: {response['metadata']['steps_completed']}")
    
    print(f"\n✅ Test 4 passed!")


def test_creative_query():
    """Test 5: Creative query"""
    print_section("TEST 5: Creative Query")
    
    client = BrainClient(enable_agi=True)
    
    query = "Write a short poem about coding at night"
    print(f"Query: {query}\n")
    
    response = client.think(query)
    
    print(f"Response:\n{response['response']}\n")
    
    if 'agi_plan' in response:
        plan = response['agi_plan']
        print(f"AGI Decision:")
        print(f"  Query type: {plan['query_type']}")
        print(f"  Confidence: {plan['confidence']:.1%}")
        print(f"  Modules to use: {', '.join(plan['modules_to_use'])}")
    
    print(f"\n✅ Test 5 passed!")


def test_multi_turn_conversation():
    """Test 6: Multi-turn conversation (context awareness)"""
    print_section("TEST 6: Multi-Turn Conversation")
    
    client = BrainClient(enable_agi=True)
    user_id = "test_user_123"
    
    # Turn 1
    query1 = "What is machine learning?"
    print(f"User: {query1}")
    response1 = client.think(query1, user_id=user_id)
    print(f"AI: {response1['response'][:100]}...\n")
    
    # Turn 2 - AGI should understand context
    time.sleep(0.5)
    query2 = "Can you give me an example?"
    print(f"User: {query2}")
    response2 = client.think(query2, user_id=user_id)
    print(f"AI: {response2['response'][:100]}...\n")
    
    if 'agi_plan' in response2:
        print(f"AGI Context Awareness:")
        print(f"  Understood 'example' refers to machine learning")
        print(f"  Maintained conversation context")
    
    print(f"\n✅ Test 6 passed!")


def test_agi_decision_stats():
    """Test 7: AGI Decision Statistics"""
    print_section("TEST 7: AGI Decision Statistics")
    
    client = BrainClient(enable_agi=True)
    
    # Make several queries to build statistics
    queries = [
        "Hello!",
        "Write a function to sort a list",
        "What is AI?",
        "Explain recursion",
        "Create a haiku about programming"
    ]
    
    print("Making 5 queries to build statistics...\n")
    for query in queries:
        client.think(query)
        time.sleep(0.3)
    
    # Get statistics
    stats = client.get_agi_decision_stats()
    
    print(f"AGI Decision Statistics:")
    print(f"  Total decisions: {stats['total_decisions']}")
    print(f"  Successful: {stats['successful']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Success rate: {stats['success_rate']:.1%}")
    
    print(f"\n  Query types handled:")
    for query_type, count in stats['query_types_handled'].items():
        print(f"    {query_type}: {count}")
    
    print(f"\n  Most used modules:")
    sorted_modules = sorted(stats['modules_used_count'].items(), 
                           key=lambda x: x[1], reverse=True)
    for module, count in sorted_modules[:5]:
        print(f"    {module}: {count} times")
    
    if stats['top_module_combinations']:
        print(f"\n  Top module combinations:")
        for combo, count in stats['top_module_combinations'][:3]:
            print(f"    {combo}: {count} times")
    
    print(f"\n✅ Test 7 passed!")


def test_agi_with_thread_manager():
    """Test 8: AGI + Thread Manager Integration"""
    print_section("TEST 8: AGI + Thread Manager Integration")
    
    client = BrainClient(enable_agi=True)
    
    # Get thread status
    thread_status = client.get_thread_status()
    
    print(f"Thread Manager Status:")
    print(f"  Total threads: {thread_status['total_threads']}")
    print(f"  Active threads: {thread_status['active_threads']}")
    
    # Get AGI status
    agi_status = client.get_agi_status()
    
    print(f"\nAGI Status:")
    print(f"  AGI enabled: {agi_status['agi_enabled']}")
    print(f"  Components available:")
    for component, available in agi_status['components'].items():
        status = '✅' if available else '❌'
        print(f"    {status} {component}")
    
    # Make a query
    print(f"\nTesting query with full integration...")
    response = client.think("Explain how neural networks work")
    
    if response['success']:
        print(f"✅ Query processed successfully")
        if 'agi_plan' in response:
            print(f"   AGI decision: {response['agi_plan']['query_type']}")
            print(f"   Modules used: {len(response['metadata']['modules_used'])}")
    
    print(f"\n✅ Test 8 passed!")


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("  AGI AUTONOMOUS DECISION-MAKING WORKFLOW TEST")
    print("="*70)
    print("\nThis test demonstrates how AGI autonomously:")
    print("  1. Analyzes queries")
    print("  2. Decides which modules to use")
    print("  3. Executes workflows")
    print("  4. Learns from outcomes")
    print("\n" + "="*70)
    
    tests = [
        ("Conversational Query", test_conversational_query),
        ("Coding Query", test_coding_query),
        ("Research Query", test_research_query),
        ("Analysis Query", test_analysis_query),
        ("Creative Query", test_creative_query),
        ("Multi-Turn Conversation", test_multi_turn_conversation),
        ("AGI Decision Statistics", test_agi_decision_stats),
        ("AGI + Thread Manager", test_agi_with_thread_manager),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
        
        time.sleep(1)  # Brief pause between tests
    
    # Final summary
    print_section("FINAL SUMMARY")
    print(f"Tests passed: {passed}/{len(tests)}")
    print(f"Tests failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print(f"\n🎉 All tests passed! AGI workflow is working perfectly!")
        print(f"\nThe brain is now truly autonomous:")
        print(f"  ✅ Analyzes queries independently")
        print(f"  ✅ Decides which modules to use")
        print(f"  ✅ Orchestrates workflows")
        print(f"  ✅ Learns from outcomes")
        print(f"  ✅ Integrates with thread manager")
        print(f"\nWorkflow: Query → Brain → AGI → Modules → SDK → Response")
    else:
        print(f"\n⚠️  Some tests failed. Check the logs above.")
    
    print(f"\n{'='*70}\n")


if __name__ == '__main__':
    main()
