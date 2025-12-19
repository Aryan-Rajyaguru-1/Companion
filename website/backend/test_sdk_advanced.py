#!/usr/bin/env python3
"""
Test Companion SDK - Advanced Features
=======================================

Demonstrates all 8 advanced capabilities through the SDK
"""

import sys
import os
import asyncio

# Add companion_baas to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sdk import BrainClient


def test_sdk_initialization():
    """Test SDK initialization"""
    print("=" * 60)
    print("TEST 1: SDK Initialization")
    print("=" * 60)
    
    client = BrainClient(app_type="chatbot")
    print(f"✅ Client initialized: {client}")
    
    # Check advanced capabilities
    caps = client.get_advanced_capabilities()
    if caps['enabled']:
        print("\n✅ ADVANCED FEATURES AVAILABLE via SDK!")
        print(f"   Capabilities: {list(caps['capabilities'].keys())}")
    else:
        print("\n⚠️  Advanced features not available")
    
    return client


def test_basic_chat(client):
    """Test basic chat"""
    print("\n" + "=" * 60)
    print("TEST 2: Basic Chat (Original SDK)")
    print("=" * 60)
    
    try:
        response = client.ask("What is 5 + 3?")
        print(f"✅ Response: {response[:100]}...")
    except Exception as e:
        print(f"❌ Error: {e}")


def test_reasoning(client):
    """Test advanced reasoning"""
    print("\n" + "=" * 60)
    print("TEST 3: Advanced Reasoning (NEW)")
    print("=" * 60)
    
    try:
        result = client.reason(
            query="If a train travels 60 km/h for 2 hours, how far does it go?",
            strategy="chain_of_thought"
        )
        print(f"✅ Strategy: {result['strategy']}")
        print(f"✅ Answer: {result['answer'][:150]}...")
        print(f"✅ Confidence: {result['confidence']}")
    except Exception as e:
        print(f"❌ Error: {e}")


def test_memory(client):
    """Test memory operations"""
    print("\n" + "=" * 60)
    print("TEST 4: Memory Persistence (NEW)")
    print("=" * 60)
    
    try:
        # Store memory
        client.remember(
            user_id="test_user",
            content="User is learning about advanced AI features",
            memory_type="preference",
            importance=0.85
        )
        print("✅ Memory stored via SDK")
        
        # Recall memory
        memories = client.recall(
            user_id="test_user",
            query="AI features"
        )
        print(f"✅ Recalled {len(memories)} memories via SDK")
        if memories:
            print(f"   Memory: {memories[0]['content'][:80]}...")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def test_learning(client):
    """Test real-time learning"""
    print("\n" + "=" * 60)
    print("TEST 5: Real-time Learning (NEW)")
    print("=" * 60)
    
    try:
        # Provide feedback
        client.provide_learning_feedback(
            user_id="test_user",
            interaction_id="sdk_test_123",
            feedback_type="rating",
            value=5
        )
        print("✅ Feedback provided via SDK")
        
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_streaming(client):
    """Test streaming responses"""
    print("\n" + "=" * 60)
    print("TEST 6: Streaming Responses (NEW)")
    print("=" * 60)
    
    try:
        print("Streaming via SDK: ", end='', flush=True)
        chunk_count = 0
        async for chunk in client.stream_think("Hello from SDK!", show_reasoning=False):
            chunk_count += 1
            if chunk.get('event') == 'token':
                print(chunk.get('content', ''), end='', flush=True)
        
        print(f"\n✅ Received {chunk_count} chunks via SDK")
        
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_agents(client):
    """Test multi-agent coordination"""
    print("\n" + "=" * 60)
    print("TEST 7: Multi-Agent Coordination (NEW)")
    print("=" * 60)
    
    print("⏭️  Skipped (requires external LLM call - can take 30+ seconds)")
    print("   Use: await client.delegate_task('Your task', use_multiple_agents=True)")
    
    # Uncomment to test (slow):
    # try:
    #     result = await client.delegate_task(
    #         task="Analyze the pros and cons of Python vs JavaScript",
    #         use_multiple_agents=True
    #     )
    #     print(f"✅ Task delegated via SDK")
    #     print(f"✅ Agents used: {result.get('agents_used', [])}")
    #     print(f"✅ Result: {result.get('result', '')[:100]}...")
    # except Exception as e:
    #     print(f"❌ Error: {e}")


def test_tools(client):
    """Test Phase 4 tools"""
    print("\n" + "=" * 60)
    print("TEST 8: Built-in Tools (Phase 4)")
    print("=" * 60)
    
    try:
        # List available tools
        tools = client.list_tools()
        print(f"✅ Available tools: {len(tools)} tools")
        print(f"   Examples: {tools[:5]}")
        
        # Execute code
        result = client.execute_code("print('Hello from SDK!')", "python")
        if result['success']:
            print(f"✅ Code execution: {result['output'].strip()}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def test_capabilities_summary(client):
    """Test capabilities summary"""
    print("\n" + "=" * 60)
    print("TEST 9: Capabilities Summary")
    print("=" * 60)
    
    try:
        caps = client.get_advanced_capabilities()
        stats = client.get_stats()
        
        print(f"✅ Phases enabled: {len(stats.get('phases_enabled', []))}")
        print(f"✅ Advanced features: {caps['enabled']}")
        
        if caps['enabled']:
            print("\n📦 Advanced Capabilities (via SDK):")
            for name, enabled in caps['capabilities'].items():
                status = "✅" if enabled else "❌"
                print(f"   {status} {name}")
    
    except Exception as e:
        print(f"❌ Error: {e}")


async def main():
    """Run all tests"""
    print("\n" + "🔧" * 30)
    print("COMPANION SDK - ADVANCED FEATURES TEST")
    print("🔧" * 30 + "\n")
    
    # Test 1: Initialization
    client = test_sdk_initialization()
    
    # Test 2: Basic chat
    test_basic_chat(client)
    
    # Test 3: Reasoning
    test_reasoning(client)
    
    # Test 4: Memory
    test_memory(client)
    
    # Test 5: Learning
    test_learning(client)
    
    # Test 6: Streaming (async)
    await test_streaming(client)
    
    # Test 7: Agents (async)
    await test_agents(client)
    
    # Test 8: Tools
    test_tools(client)
    
    # Test 9: Summary
    test_capabilities_summary(client)
    
    print("\n" + "=" * 60)
    print("✅ ALL SDK TESTS COMPLETE!")
    print("=" * 60)
    
    print("\n💡 SDK Usage Examples:")
    print("   from companion_baas.sdk import BrainClient")
    print("   client = BrainClient(app_type='chatbot')")
    print("")
    print("   # Basic chat")
    print("   response = client.ask('Hello!')")
    print("")
    print("   # Advanced reasoning")
    print("   result = client.reason('Complex question', strategy='chain_of_thought')")
    print("")
    print("   # Memory operations")
    print("   client.remember('user123', 'Important info', importance=0.9)")
    print("   memories = client.recall('user123', 'query')")
    print("")
    print("   # Streaming")
    print("   async for chunk in client.stream_think('Question'):")
    print("       print(chunk['content'], end='')")
    print("")
    print("   # Multi-agent tasks")
    print("   result = await client.delegate_task('Complex task')")
    print("")
    print("   # Check capabilities")
    print("   caps = client.get_advanced_capabilities()")


if __name__ == "__main__":
    asyncio.run(main())
