#!/usr/bin/env python3
"""
Companion SDK - Complete Demo
==============================

Shows all features working together in a real-world scenario
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sdk import BrainClient


async def main():
    """Complete SDK demonstration"""
    
    print("=" * 70)
    print("🧠 COMPANION BAAS SDK - COMPLETE DEMO")
    print("=" * 70)
    
    # Initialize
    print("\n1️⃣  Initializing Brain Client...")
    client = BrainClient(app_type="assistant")
    print(f"   ✅ Client ready: {client}")
    
    # Check capabilities
    print("\n2️⃣  Checking Capabilities...")
    caps = client.get_advanced_capabilities()
    print(f"   ✅ Advanced features: {caps['enabled']}")
    print(f"   ✅ Total capabilities: {len(caps['capabilities'])}")
    
    # Basic chat
    print("\n3️⃣  Basic Chat...")
    response = client.ask("What is your purpose?")
    print(f"   Q: What is your purpose?")
    print(f"   A: {response[:150]}...")
    
    # Memory - Store user preferences
    print("\n4️⃣  Memory System...")
    user_id = "demo_user"
    
    client.remember(
        user_id,
        "User is interested in AI and machine learning",
        memory_type="preference",
        importance=0.9
    )
    print("   ✅ Stored: User interests")
    
    client.remember(
        user_id,
        "User prefers Python for coding projects",
        memory_type="preference",
        importance=0.8
    )
    print("   ✅ Stored: Programming preference")
    
    # Recall memories
    memories = client.recall(user_id, "programming AI")
    print(f"   ✅ Recalled: {len(memories)} relevant memories")
    
    # Learning - Provide feedback
    print("\n5️⃣  Real-time Learning...")
    client.provide_learning_feedback(
        user_id=user_id,
        interaction_id="demo_001",
        feedback_type="rating",
        value=5
    )
    print("   ✅ Feedback recorded: 5-star rating")
    
    # Code execution
    print("\n6️⃣  Code Execution...")
    result = client.execute_code(
        "result = sum([x**2 for x in range(1, 6)]); print(f'Sum of squares 1-5: {result}')",
        "python"
    )
    print(f"   ✅ Executed: {result['output'].strip()}")
    
    # Built-in tools
    print("\n7️⃣  Built-in Tools...")
    tools = client.list_tools()
    print(f"   ✅ Available tools: {len(tools)}")
    
    math_result = client.call_tool("multiply", 7, 8)
    print(f"   ✅ Tool result: 7 × 8 = {math_result}")
    
    # Advanced reasoning
    print("\n8️⃣  Advanced Reasoning...")
    reasoning_result = client.reason(
        "If a train travels at 60 km/h for 2.5 hours, how far does it travel?",
        strategy="chain_of_thought"
    )
    print(f"   Strategy: {reasoning_result['strategy']}")
    print(f"   Answer: {reasoning_result['answer'][:100]}...")
    print(f"   Confidence: {reasoning_result['confidence']}")
    
    # Streaming demonstration
    print("\n9️⃣  Streaming Response...")
    print("   Question: Tell me a fun fact about Python")
    print("   Response: ", end='', flush=True)
    
    token_count = 0
    async for chunk in client.stream_think(
        "Tell me one interesting fact about Python programming language",
        show_reasoning=False
    ):
        if chunk['event'] == 'token':
            print(chunk['content'], end='', flush=True)
            token_count += 1
    
    print(f"\n   ✅ Streamed {token_count} tokens")
    
    # Final statistics
    print("\n🔟 Final Statistics...")
    stats = client.get_stats()
    print(f"   ✅ Total requests: {stats['total_requests']}")
    print(f"   ✅ Phases enabled: {len(stats['phases_enabled'])}")
    print(f"   ✅ Advanced features: {stats.get('advanced_features_enabled', False)}")
    
    # Summary
    print("\n" + "=" * 70)
    print("✅ DEMO COMPLETE!")
    print("=" * 70)
    print("\n📊 What was demonstrated:")
    print("   ✅ Client initialization")
    print("   ✅ Capability checking")
    print("   ✅ Basic chat")
    print("   ✅ Memory storage & retrieval")
    print("   ✅ Real-time learning")
    print("   ✅ Code execution")
    print("   ✅ Built-in tools")
    print("   ✅ Advanced reasoning")
    print("   ✅ Streaming responses")
    print("\n💡 All features working with 100% FREE Bytez integration!")
    print("\n🚀 Ready for production use!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
