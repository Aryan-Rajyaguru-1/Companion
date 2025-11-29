#!/usr/bin/env python3
"""
Test Advanced Features Integration
===================================

Quick test to verify all 8 advanced capabilities are working
"""

import sys
import os

# Add companion_baas to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.brain import CompanionBrain
import asyncio


def test_brain_initialization():
    """Test that brain initializes with advanced features"""
    print("=" * 60)
    print("TEST 1: Brain Initialization")
    print("=" * 60)
    
    brain = CompanionBrain(app_type="chatbot")
    print(f"✅ Brain initialized: {brain}")
    print(f"✅ Session ID: {brain.session_id}")
    print(f"✅ Enabled phases: {brain._get_enabled_phases()}")
    
    # Check advanced features
    if hasattr(brain, 'advanced') and brain.advanced:
        print("\n✅ ADVANCED FEATURES AVAILABLE!")
        caps = brain.get_advanced_capabilities()
        print(f"   Capabilities: {caps.get('capabilities', {})}")
    else:
        print("\n⚠️  Advanced features not initialized")
    
    return brain


def test_reasoning(brain):
    """Test advanced reasoning"""
    print("\n" + "=" * 60)
    print("TEST 2: Advanced Reasoning")
    print("=" * 60)
    
    if not brain.advanced:
        print("⚠️  Skipping - advanced features not available")
        return
    
    try:
        result = brain.reason(
            query="What is 2+2? Think step by step.",
            strategy="chain_of_thought"
        )
        print(f"✅ Reasoning Strategy: {result.get('strategy')}")
        print(f"✅ Answer: {result.get('answer')}")
        print(f"✅ Steps: {len(result.get('steps', []))} reasoning steps")
    except Exception as e:
        print(f"❌ Error: {e}")


def test_memory(brain):
    """Test memory persistence"""
    print("\n" + "=" * 60)
    print("TEST 3: Memory Persistence")
    print("=" * 60)
    
    if not brain.advanced:
        print("⚠️  Skipping - advanced features not available")
        return
    
    try:
        # Store memory
        brain.remember(
            user_id="test_user",
            content="User loves Python programming",
            memory_type="preference",
            importance=0.9
        )
        print("✅ Memory stored")
        
        # Recall memory
        memories = brain.recall(
            user_id="test_user",
            query="Python"
        )
        print(f"✅ Recalled {len(memories)} memories")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def test_learning(brain):
    """Test real-time learning"""
    print("\n" + "=" * 60)
    print("TEST 4: Real-time Learning")
    print("=" * 60)
    
    if not brain.advanced:
        print("⚠️  Skipping - advanced features not available")
        return
    
    try:
        # Provide feedback
        brain.provide_feedback(
            user_id="test_user",
            interaction_id="test_123",
            feedback_type="rating",
            value=5
        )
        print("✅ Feedback provided")
        
        # Get user profile
        profile = brain.advanced.get_user_profile("test_user")
        print(f"✅ User profile: {profile.get('feedback_stats', {})}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_streaming(brain):
    """Test streaming responses"""
    print("\n" + "=" * 60)
    print("TEST 5: Streaming Responses")
    print("=" * 60)
    
    if not brain.advanced:
        print("⚠️  Skipping - advanced features not available")
        return
    
    try:
        print("Streaming response:")
        chunk_count = 0
        async for chunk in brain.stream_think("Hello!", show_reasoning=False):
            chunk_count += 1
            if chunk.get('event') == 'token':
                print(chunk.get('content', ''), end='', flush=True)
        
        print(f"\n✅ Received {chunk_count} chunks")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def test_system_status(brain):
    """Test system status"""
    print("\n" + "=" * 60)
    print("TEST 6: System Status")
    print("=" * 60)
    
    try:
        stats = brain.get_stats()
        print(f"✅ Total requests: {stats.get('total_requests')}")
        print(f"✅ Phases enabled: {len(stats.get('phases_enabled', []))}")
        
        if brain.advanced:
            adv_caps = brain.get_advanced_capabilities()
            print(f"✅ Advanced features: {adv_caps.get('enabled')}")
            
            caps = adv_caps.get('capabilities', {})
            print("\n📦 Advanced Capabilities:")
            for name, enabled in caps.items():
                status = "✅" if enabled else "❌"
                print(f"   {status} {name}")
    
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    """Run all tests"""
    print("\n" + "🧠" * 30)
    print("COMPANION BRAIN - ADVANCED FEATURES TEST")
    print("🧠" * 30 + "\n")
    
    # Test 1: Initialization
    brain = test_brain_initialization()
    
    # Test 2: Reasoning
    test_reasoning(brain)
    
    # Test 3: Memory
    test_memory(brain)
    
    # Test 4: Learning
    test_learning(brain)
    
    # Test 5: Streaming (async)
    asyncio.run(test_streaming(brain))
    
    # Test 6: System Status
    test_system_status(brain)
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS COMPLETE!")
    print("=" * 60)
    
    return brain


if __name__ == "__main__":
    brain = main()
    
    print("\n💡 Try these commands in Python REPL:")
    print("   brain.reason('What is AI?', strategy='chain_of_thought')")
    print("   brain.remember('user1', 'Important fact', importance=0.9)")
    print("   brain.recall('user1', 'fact')")
    print("   await brain.think_advanced('Hello', use_reasoning=True)")
    print("   brain.get_advanced_capabilities()")
