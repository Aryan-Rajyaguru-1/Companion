#!/usr/bin/env python3
"""
Test script for Tier 3 brain features:
- Semantic cache with embeddings
- Multi-model consensus querying
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from companion_baas.core.brain import CompanionBrain


async def test_semantic_cache():
    """Test semantic cache with similar queries"""
    print("\n" + "="*60)
    print("🧪 TEST 1: Semantic Cache")
    print("="*60)
    
    brain = CompanionBrain(app_type="test")
    
    # First query - should miss cache
    query1 = "What is machine learning?"
    print(f"\n📝 Query 1: {query1}")
    response1 = brain.think(query1, {})
    print(f"✅ Response: {response1['response'][:100]}...")
    print(f"📊 Cached: {response1.get('cached', False)}")
    
    # Exact same query - should hit legacy cache
    print(f"\n📝 Query 2 (exact same): {query1}")
    response2 = brain.think(query1, {})
    print(f"✅ Response: {response2['response'][:100]}...")
    print(f"📊 Cached: {response2.get('cached', False)}")
    print(f"📊 Cache type: {response2.get('cache_type', 'none')}")
    
    # Semantically similar query - should hit semantic cache
    query3 = "Can you explain what ML is?"
    print(f"\n📝 Query 3 (semantically similar): {query3}")
    response3 = brain.think(query3, {})
    print(f"✅ Response: {response3['response'][:100]}...")
    print(f"📊 Cached: {response3.get('cached', False)}")
    print(f"📊 Cache type: {response3.get('cache_type', 'none')}")
    
    # Get semantic cache stats
    cache_stats = brain.get_semantic_cache_stats()
    print(f"\n📈 Semantic Cache Stats:")
    print(f"   Hits: {cache_stats['hits']}")
    print(f"   Misses: {cache_stats['misses']}")
    print(f"   Hit Rate: {cache_stats['hit_rate']:.1f}%")
    print(f"   Cache Size: {cache_stats['cache_size']}")
    
    return cache_stats['hits'] > 0  # Should have at least one semantic hit


async def test_multi_model_consensus():
    """Test multi-model consensus with 3 models"""
    print("\n" + "="*60)
    print("🧪 TEST 2: Multi-Model Consensus")
    print("="*60)
    
    brain = CompanionBrain(app_type="test")
    
    # Query with consensus (3 models)
    query = "What are the key principles of object-oriented programming?"
    print(f"\n📝 Query: {query}")
    print("🔄 Querying 3 models in parallel...")
    
    result = await brain.query_with_consensus(
        query,
        models=['qwen-4b', 'phi-2-reasoner', 'deepseek-coder'],
        min_agreement=0.6
    )
    
    print(f"\n✅ Combined Response: {result['response'][:150]}...")
    print(f"📊 Confidence: {result['confidence']:.2%}")
    print(f"📊 Agreement Score: {result['agreement_score']:.2%}")
    print(f"📊 Models Used: {', '.join(result['models_used'])}")
    print(f"📊 Cache Hit: {result['cache_hit']}")
    
    # Show individual results if available
    if result['individual_results']:
        print(f"\n📋 Individual Model Responses:")
        for i, res in enumerate(result['individual_results'], 1):
            print(f"   {i}. {res['model']}: {res['response'][:80]}...")
    
    # Get consensus stats
    consensus_stats = brain.get_consensus_stats()
    print(f"\n📈 Consensus Stats:")
    print(f"   Total Queries: {consensus_stats['consensus_queries']}")
    print(f"   Total Models Queried: {consensus_stats['total_models_queried']}")
    print(f"   Avg Models/Query: {consensus_stats['avg_models_per_query']:.1f}")
    
    return result['confidence'] > 0.5 and len(result['models_used']) >= 2


async def test_tier3_stats_integration():
    """Test that Tier 3 stats appear in get_stats()"""
    print("\n" + "="*60)
    print("🧪 TEST 3: Stats Integration")
    print("="*60)
    
    brain = CompanionBrain(app_type="test")
    
    # Do a few operations
    brain.think("Test query 1", {})
    brain.think("Test query 1", {})  # Should hit cache
    await brain.query_with_consensus("Test consensus query")
    
    # Get full stats
    stats = brain.get_stats()
    
    print("\n📊 Checking Tier 3 stats in get_stats():")
    
    # Check semantic cache stats
    if 'semantic_cache' in stats:
        print(f"✅ semantic_cache present:")
        print(f"   {stats['semantic_cache']}")
    else:
        print("❌ semantic_cache missing!")
        return False
    
    # Check consensus stats
    if 'multi_model_consensus' in stats:
        print(f"✅ multi_model_consensus present:")
        print(f"   {stats['multi_model_consensus']}")
    else:
        print("❌ multi_model_consensus missing!")
        return False
    
    # Check base stats still present
    required_keys = ['session_id', 'app_type', 'success_rate', 'circuit_breakers']
    missing = [k for k in required_keys if k not in stats]
    if missing:
        print(f"❌ Missing base stats: {missing}")
        return False
    else:
        print(f"✅ All base stats present")
    
    return True


async def test_consensus_caching():
    """Test that consensus results are cached"""
    print("\n" + "="*60)
    print("🧪 TEST 4: Consensus Result Caching")
    print("="*60)
    
    brain = CompanionBrain(app_type="test")
    
    query = "What is recursion in programming?"
    
    # First consensus query - should query models
    print(f"\n📝 First consensus query: {query}")
    result1 = await brain.query_with_consensus(query)
    print(f"✅ Cache Hit: {result1['cache_hit']}")
    print(f"📊 Models Queried: {len(result1['models_used'])}")
    
    # Second consensus query - should hit cache
    print(f"\n📝 Second consensus query (same): {query}")
    result2 = await brain.query_with_consensus(query)
    print(f"✅ Cache Hit: {result2['cache_hit']}")
    print(f"📊 Models Queried: {len(result2.get('individual_results', []))}")
    
    if result2['cache_hit']:
        print("✅ Consensus caching works!")
        return True
    else:
        print("⚠️ Expected cache hit on second query")
        return False


async def main():
    """Run all Tier 3 tests"""
    print("\n" + "="*80)
    print("🚀 TIER 3 FEATURE TESTING")
    print("="*80)
    print("Testing: Semantic Cache + Multi-Model Consensus")
    
    results = []
    
    try:
        # Test 1: Semantic cache
        result1 = await test_semantic_cache()
        results.append(("Semantic Cache", result1))
        
        # Test 2: Multi-model consensus
        result2 = await test_multi_model_consensus()
        results.append(("Multi-Model Consensus", result2))
        
        # Test 3: Stats integration
        result3 = await test_tier3_stats_integration()
        results.append(("Stats Integration", result3))
        
        # Test 4: Consensus caching
        result4 = await test_consensus_caching()
        results.append(("Consensus Caching", result4))
        
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\n{'='*80}")
    print(f"Results: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print("="*80)
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
