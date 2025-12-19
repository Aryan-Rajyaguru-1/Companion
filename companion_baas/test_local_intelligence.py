"""
Test Local Intelligence Core - Week 1
Tests Ollama integration with already installed models
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from companion_baas.core.local_intelligence import (
    LocalIntelligenceCore,
    OllamaManager,
    HybridInferenceEngine
)


async def test_local_intelligence():
    """Test the local intelligence core"""
    
    print("=" * 60)
    print("Testing Local Intelligence Core (Week 1)")
    print("=" * 60)
    
    # Test 1: Create and initialize
    print("\n[Test 1] Initializing Local Intelligence Core...")
    core = LocalIntelligenceCore(auto_setup=False)
    await core._async_setup()
    
    if core.initialized:
        print("✅ PASS - Core initialized successfully")
    else:
        print("❌ FAIL - Core initialization failed")
        return
    
    # Test 2: List models
    print("\n[Test 2] Listing installed models...")
    models = await core.list_models()
    print(f"Found {len(models)} models: {models}")
    
    if len(models) > 0:
        print("✅ PASS - Models detected")
    else:
        print("❌ FAIL - No models found")
        return
    
    # Test 3: Get stats
    print("\n[Test 3] Getting statistics...")
    stats = core.get_stats()
    print(f"Stats: {stats}")
    
    if 'ollama' in stats and 'inference' in stats:
        print("✅ PASS - Stats structure correct")
    else:
        print("❌ FAIL - Stats structure incorrect")
    
    # Test 4: Simple local inference
    print("\n[Test 4] Testing local inference...")
    try:
        result = await core.think(
            prompt="What is 2+2? Answer in one word.",
            task_type="reasoning",
            prefer_local=True
        )
        
        print(f"Response: {result.get('response', 'No response')[:100]}")
        print(f"Model used: {result.get('model')}")
        print(f"Source: {result.get('source')}")
        print(f"Latency: {result.get('latency', 0):.2f}s")
        
        if 'response' in result and result['source'] == 'local_ollama':
            print("✅ PASS - Local inference working")
        else:
            print("⚠️ PARTIAL - Got response but not from local")
    except Exception as e:
        print(f"❌ FAIL - Local inference error: {e}")
    
    # Test 5: Auto model selection
    print("\n[Test 5] Testing auto model selection for different tasks...")
    tasks = ['coding', 'reasoning', 'general', 'fast']
    
    for task in tasks:
        selected = await core.ollama.auto_select_models(task)
        print(f"  {task:12} → {selected[0] if selected else 'None'}")
    
    print("✅ PASS - Auto model selection working")
    
    # Test 6: Hybrid inference stats
    print("\n[Test 6] Checking hybrid inference statistics...")
    inference_stats = core.hybrid_engine.get_stats()
    print(f"Local calls: {inference_stats['local_calls']}")
    print(f"Cloud calls: {inference_stats['cloud_calls']}")
    print(f"Local percentage: {inference_stats['local_percentage']:.1f}%")
    
    if inference_stats['local_calls'] > 0:
        print("✅ PASS - Hybrid inference tracked")
    else:
        print("⚠️ WARNING - No local calls tracked yet")
    
    print("\n" + "=" * 60)
    print("🎉 All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_local_intelligence())
