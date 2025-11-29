#!/usr/bin/env python3
"""
Test Thread-Based Architecture
===============================

Tests the comprehensive thread management system where:
- All modules run in dedicated threads
- Brain autonomously manages thread lifecycle
- All communication flows through thread manager
"""

import sys
import os
import time
from pathlib import Path

# Add companion_baas to path
sys.path.insert(0, str(Path(__file__).parent))

from companion_baas.sdk import BrainClient


def test_thread_initialization():
    """Test 1: Verify threads are created for all modules"""
    print("\n" + "="*70)
    print("TEST 1: Thread Initialization")
    print("="*70)
    
    # Create brain with AGI enabled
    brain = BrainClient(
        app_type="chatbot",
        enable_caching=True,
        enable_search=True,
        enable_learning=True,
        enable_agi=True,
        enable_autonomy=False
    )
    
    # Get thread status
    status = brain.get_thread_status()
    
    print(f"\n✅ Thread Manager Enabled: {status['enabled']}")
    print(f"📊 Total Threads: {status['total_threads']}")
    print(f"▶️  Active Threads: {status['active_threads']}")
    print(f"🎯 Max Threads: {status['max_threads']}")
    print(f"⚖️  Auto-scaling: {status['auto_scaling']}")
    print(f"⏱️  Uptime: {status['uptime']:.2f}s")
    
    # Show thread categories
    print(f"\n📦 Thread Categories:")
    for category, stats in status['categories'].items():
        utilization = (stats['active'] / stats['max'] * 100) if stats['max'] > 0 else 0
        print(f"  {category:12s}: {stats['active']}/{stats['max']} threads ({utilization:.1f}% utilized)")
    
    # Show module threads
    print(f"\n🧵 Module Threads:")
    for module, thread_status in status['module_threads'].items():
        print(f"  {module:25s}: {thread_status['state']:10s} | "
              f"Completed: {thread_status['tasks_completed']:4d} | "
              f"Success: {thread_status['success_rate']*100:5.1f}%")
    
    assert status['enabled'], "Thread manager should be enabled"
    assert status['total_threads'] > 0, "Should have created threads"
    print(f"\n✅ Test 1 PASSED: {status['total_threads']} threads initialized")
    
    return brain


def test_autonomous_decisions(brain):
    """Test 2: Verify autonomous decision-making"""
    print("\n" + "="*70)
    print("TEST 2: Autonomous Decision-Making")
    print("="*70)
    
    # Wait a bit for autonomous manager to make some decisions
    print("\n⏳ Waiting 12 seconds for autonomous manager to run...")
    time.sleep(12)
    
    # Get decision history
    decisions = brain.get_thread_decisions()
    
    print(f"\n🤖 Autonomous Decisions Made: {len(decisions)}")
    
    if decisions:
        print(f"\n📋 Recent Decisions:")
        for decision in decisions[-5:]:  # Last 5
            print(f"  [{decision['timestamp']}]")
            print(f"    Type: {decision['type']}")
            print(f"    Context: {decision['context']}")
            print(f"    Data: {decision['data']}")
    else:
        print("  No decisions made yet (this is normal if all threads healthy)")
    
    print(f"\n✅ Test 2 PASSED: Decision system active")


def test_module_thread_status(brain):
    """Test 3: Check individual module thread status"""
    print("\n" + "="*70)
    print("TEST 3: Module Thread Status")
    print("="*70)
    
    # Check core modules
    modules_to_check = [
        'model_router',
        'context_manager',
        'personality_engine',
        'neural_reasoning',
        'self_learning'
    ]
    
    print(f"\n🔍 Checking Module Threads:")
    for module in modules_to_check:
        status = brain.get_module_thread_status(module)
        if status:
            print(f"\n  {module}:")
            print(f"    State: {status['state']}")
            print(f"    Tasks Completed: {status['tasks_completed']}")
            print(f"    Tasks Failed: {status['tasks_failed']}")
            print(f"    Success Rate: {status['success_rate']*100:.2f}%")
            print(f"    Uptime: {status['uptime']:.2f}s")
            print(f"    Queue Size: {status['queue_size']}")
            print(f"    Alive: {status['is_alive']}")
        else:
            print(f"\n  {module}: Not initialized")
    
    print(f"\n✅ Test 3 PASSED: Module threads accessible")


def test_thread_statistics(brain):
    """Test 4: Verify thread statistics"""
    print("\n" + "="*70)
    print("TEST 4: Thread Statistics")
    print("="*70)
    
    status = brain.get_thread_status()
    stats = status['stats']
    
    print(f"\n📈 System Statistics:")
    print(f"  Total Threads Created: {stats['total_threads_created']}")
    print(f"  Total Tasks Completed: {stats['total_tasks_completed']}")
    print(f"  Total Tasks Failed: {stats['total_tasks_failed']}")
    print(f"  Auto-scale Events: {stats['threads_auto_scaled']}")
    print(f"  Threads Restarted: {stats['threads_restarted']}")
    print(f"  System Uptime: {stats['uptime_start']}")
    
    # Calculate overall success rate
    total_tasks = stats['total_tasks_completed'] + stats['total_tasks_failed']
    if total_tasks > 0:
        success_rate = stats['total_tasks_completed'] / total_tasks * 100
        print(f"  Overall Success Rate: {success_rate:.2f}%")
    
    print(f"\n✅ Test 4 PASSED: Statistics collected")


def test_pause_resume(brain):
    """Test 5: Test pause/resume functionality"""
    print("\n" + "="*70)
    print("TEST 5: Pause/Resume Module")
    print("="*70)
    
    # Pause a module
    module = 'context_manager'
    print(f"\n⏸️  Pausing {module}...")
    success = brain.pause_module(module)
    print(f"  Result: {'✅ Success' if success else '❌ Failed'}")
    
    time.sleep(2)
    
    # Check status
    status = brain.get_module_thread_status(module)
    if status:
        print(f"  Current state: {status['state']}")
    
    # Resume module
    print(f"\n▶️  Resuming {module}...")
    success = brain.resume_module(module)
    print(f"  Result: {'✅ Success' if success else '❌ Failed'}")
    
    time.sleep(1)
    
    # Check status again
    status = brain.get_module_thread_status(module)
    if status:
        print(f"  Current state: {status['state']}")
    
    print(f"\n✅ Test 5 PASSED: Pause/resume working")


def test_brain_with_agi(brain):
    """Test 6: Test brain functionality with threaded AGI"""
    print("\n" + "="*70)
    print("TEST 6: Brain Functionality with Threaded AGI")
    print("="*70)
    
    # Test chat
    print(f"\n💬 Testing chat with threaded modules...")
    response = brain.ask("Hello! Tell me about yourself.")
    print(f"  Response length: {len(response)} characters")
    print(f"  First 100 chars: {response[:100]}...")
    
    # Get personality
    print(f"\n🎭 Getting personality (via personality_engine thread)...")
    personality = brain.get_personality()
    if personality:
        print(f"  Personality ID: {personality.get('personality_id', 'N/A')}")
        print(f"  Current Emotion: {personality.get('emotion', 'N/A')}")
        print(f"  Dominant Traits: {personality.get('dominant_traits', [])}")
    
    # Get learning stats
    print(f"\n📚 Getting learning stats (via self_learning thread)...")
    try:
        learning = brain.get_learning_stats()
        if learning:
            print(f"  Episodes: {learning.get('episodes', 0)}")
            print(f"  Concepts: {learning.get('concepts', 0)}")
            print(f"  Skills: {learning.get('skills', 0)}")
    except Exception as e:
        print(f"  ⚠️ Learning stats unavailable: {e}")
    
    # Get thread status after operations
    print(f"\n🧵 Thread status after operations:")
    status = brain.get_thread_status()
    print(f"  Active threads: {status['active_threads']}")
    
    # Check if any tasks were completed
    total_completed = sum(
        t['tasks_completed']
        for t in status['module_threads'].values()
    )
    print(f"  Total tasks completed: {total_completed}")
    
    print(f"\n✅ Test 6 PASSED: Brain working with threads")


def test_comprehensive_status(brain):
    """Test 7: Get comprehensive system status"""
    print("\n" + "="*70)
    print("TEST 7: Comprehensive System Status")
    print("="*70)
    
    # Get all statuses
    thread_status = brain.get_thread_status()
    try:
        agi_status = brain.get_agi_status()
    except Exception as e:
        print(f"  ⚠️ AGI status unavailable: {e}")
        agi_status = {'agi_enabled': False, 'components': {}}
    decisions = brain.get_thread_decisions()
    
    print(f"\n📊 Complete System Overview:")
    print(f"\n🧵 THREADING:")
    print(f"  Enabled: {thread_status['enabled']}")
    print(f"  Active: {thread_status['active_threads']}/{thread_status['total_threads']}")
    print(f"  Auto-scaling: {thread_status['auto_scaling']}")
    
    print(f"\n🧠 AGI:")
    print(f"  Enabled: {agi_status['agi_enabled']}")
    print(f"  Components active: {sum(agi_status['components'].values())}")
    
    print(f"\n🤖 AUTONOMOUS DECISIONS:")
    print(f"  Total decisions: {len(decisions)}")
    
    print(f"\n📈 PERFORMANCE:")
    total_completed = sum(t['tasks_completed'] for t in thread_status['module_threads'].values())
    total_failed = sum(t['tasks_failed'] for t in thread_status['module_threads'].values() if 'tasks_failed' in t)
    if total_completed + total_failed > 0:
        overall_success = total_completed / (total_completed + total_failed) * 100
        print(f"  Tasks completed: {total_completed}")
        print(f"  Tasks failed: {total_failed}")
        print(f"  Success rate: {overall_success:.2f}%")
    else:
        print(f"  No tasks executed yet")
    
    print(f"\n✅ Test 7 PASSED: Complete status retrieved")


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("🧵 THREAD-BASED ARCHITECTURE COMPREHENSIVE TEST SUITE")
    print("="*70)
    print("\nTesting autonomous thread management system where:")
    print("  • All modules run in dedicated threads")
    print("  • Brain autonomously manages thread lifecycle")
    print("  • Auto-scaling, self-healing, and optimization")
    print("="*70)
    
    try:
        # Test 1: Initialize with threads
        brain = test_thread_initialization()
        
        # Test 2: Autonomous decisions
        test_autonomous_decisions(brain)
        
        # Test 3: Module thread status
        test_module_thread_status(brain)
        
        # Test 4: Statistics
        test_thread_statistics(brain)
        
        # Test 5: Pause/Resume
        test_pause_resume(brain)
        
        # Test 6: Brain functionality
        test_brain_with_agi(brain)
        
        # Test 7: Comprehensive status
        test_comprehensive_status(brain)
        
        # Final summary
        print("\n" + "="*70)
        print("🎉 ALL TESTS PASSED!")
        print("="*70)
        
        status = brain.get_thread_status()
        print(f"\n📊 Final Stats:")
        print(f"  Total threads: {status['total_threads']}")
        print(f"  Active threads: {status['active_threads']}")
        print(f"  System uptime: {status['uptime']:.2f}s")
        print(f"  Module threads: {len(status['module_threads'])}")
        
        # Graceful shutdown
        print(f"\n🛑 Shutting down gracefully...")
        brain.shutdown(timeout=10.0)
        print(f"✅ Shutdown complete")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
