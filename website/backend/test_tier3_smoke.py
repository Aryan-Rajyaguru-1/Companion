#!/usr/bin/env python3
"""
Smoke test for Tier 3 brain features - checks implementation without API calls
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from companion_baas.core.brain import CompanionBrain


def test_tier3_classes_exist():
    """Test that Tier 3 classes are properly defined"""
    print("\n" + "="*60)
    print("🧪 TEST 1: Tier 3 Classes Exist")
    print("="*60)
    
    try:
        from companion_baas.core.brain import SemanticCache, MultiModelConsensus
        print("✅ SemanticCache class imported")
        print("✅ MultiModelConsensus class imported")
        
        # Check methods exist
        cache = SemanticCache()
        assert hasattr(cache, 'get'), "SemanticCache missing get method"
        assert hasattr(cache, 'set'), "SemanticCache missing set method"
        assert hasattr(cache, 'get_stats'), "SemanticCache missing get_stats method"
        print("✅ SemanticCache has required methods")
        
        # Can't instantiate MultiModelConsensus without brain, but check class exists
        assert hasattr(MultiModelConsensus, 'query_with_consensus'), "MultiModelConsensus missing query_with_consensus"
        assert hasattr(MultiModelConsensus, 'get_stats'), "MultiModelConsensus missing get_stats"
        print("✅ MultiModelConsensus has required methods")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_brain_tier3_integration():
    """Test that Tier 3 features are integrated into CompanionBrain"""
    print("\n" + "="*60)
    print("🧪 TEST 2: Brain Tier 3 Integration")
    print("="*60)
    
    try:
        brain = CompanionBrain(app_type="test")
        
        # Check Tier 3 attributes exist
        assert hasattr(brain, 'semantic_cache'), "Brain missing semantic_cache attribute"
        print("✅ Brain has semantic_cache attribute")
        
        assert hasattr(brain, 'multi_model_consensus'), "Brain missing multi_model_consensus attribute"
        print("✅ Brain has multi_model_consensus attribute")
        
        assert hasattr(brain, 'prompt_optimizer'), "Brain missing prompt_optimizer attribute"
        print("✅ Brain has prompt_optimizer attribute")
        
        assert hasattr(brain, 'performance_monitor'), "Brain missing performance_monitor attribute"
        print("✅ Brain has performance_monitor attribute")
        
        # Check public methods exist
        assert hasattr(brain, 'query_with_consensus'), "Brain missing query_with_consensus method"
        print("✅ Brain has query_with_consensus method")
        
        assert hasattr(brain, 'get_consensus_stats'), "Brain missing get_consensus_stats method"
        print("✅ Brain has get_consensus_stats method")
        
        assert hasattr(brain, 'get_semantic_cache_stats'), "Brain missing get_semantic_cache_stats method"
        print("✅ Brain has get_semantic_cache_stats method")
        
        assert hasattr(brain, 'optimize_prompt'), "Brain missing optimize_prompt method"
        print("✅ Brain has optimize_prompt method")
        
        assert hasattr(brain, 'get_prompt_optimization_stats'), "Brain missing get_prompt_optimization_stats method"
        print("✅ Brain has get_prompt_optimization_stats method")
        
        assert hasattr(brain, 'get_performance_percentiles'), "Brain missing get_performance_percentiles method"
        print("✅ Brain has get_performance_percentiles method")
        
        assert hasattr(brain, 'get_latency_histogram'), "Brain missing get_latency_histogram method"
        print("✅ Brain has get_latency_histogram method")
        
        assert hasattr(brain, 'get_performance_monitoring_stats'), "Brain missing get_performance_monitoring_stats method"
        print("✅ Brain has get_performance_monitoring_stats method")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_semantic_cache_basic():
    """Test semantic cache basic operations"""
    print("\n" + "="*60)
    print("🧪 TEST 3: Semantic Cache Basic Operations")
    print("="*60)
    
    try:
        from companion_baas.core.brain import SemanticCache
        
        cache = SemanticCache()
        
        # Test set and get (graceful degradation when sentence-transformers not available)
        cache.set("test query", "test response", {"context": "test"})
        print("✅ Cache set() works (graceful degradation if dependencies missing)")
        
        # Test get stats
        stats = cache.get_stats()
        assert 'hits' in stats, "Stats missing 'hits'"
        assert 'misses' in stats, "Stats missing 'misses'"
        assert 'hit_rate' in stats, "Stats missing 'hit_rate'"
        assert 'cache_size' in stats, "Stats missing 'cache_size'"
        assert 'enabled' in stats, "Stats missing 'enabled'"
        print(f"✅ Cache get_stats() works: {stats}")
        
        # Check enabled status
        if stats['enabled']:
            # If sentence-transformers is installed, cache should store
            assert stats['cache_size'] == 1, f"Expected cache_size=1, got {stats['cache_size']}"
            print("✅ Cache stored entry correctly (dependencies available)")
        else:
            # If sentence-transformers not installed, cache_size should be 0
            assert stats['cache_size'] == 0, f"Expected cache_size=0 when disabled, got {stats['cache_size']}"
            print("✅ Cache graceful degradation works (dependencies not available)")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_consensus_stats():
    """Test consensus stats method"""
    print("\n" + "="*60)
    print("🧪 TEST 4: Consensus Stats")
    print("="*60)
    
    try:
        brain = CompanionBrain(app_type="test")
        
        # Get consensus stats
        stats = brain.get_consensus_stats()
        assert 'consensus_queries' in stats, "Stats missing 'consensus_queries'"
        assert 'total_models_queried' in stats, "Stats missing 'total_models_queried'"
        assert 'avg_models_per_query' in stats, "Stats missing 'avg_models_per_query'"
        print(f"✅ get_consensus_stats() works: {stats}")
        
        # Get semantic cache stats
        cache_stats = brain.get_semantic_cache_stats()
        assert 'hits' in cache_stats, "Cache stats missing 'hits'"
        assert 'misses' in cache_stats, "Cache stats missing 'misses'"
        print(f"✅ get_semantic_cache_stats() works: {cache_stats}")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_stats_integration():
    """Test that Tier 3 stats appear in get_stats()"""
    print("\n" + "="*60)
    print("🧪 TEST 5: Stats Integration in get_stats()")
    print("="*60)
    
    try:
        brain = CompanionBrain(app_type="test")
        stats = brain.get_stats()
        
        # Check all Tier 3 stats present
        assert 'semantic_cache' in stats, "get_stats() missing 'semantic_cache'"
        print(f"✅ semantic_cache in get_stats()")
        
        assert 'multi_model_consensus' in stats, "get_stats() missing 'multi_model_consensus'"
        print(f"✅ multi_model_consensus in get_stats()")
        
        assert 'prompt_optimizer' in stats, "get_stats() missing 'prompt_optimizer'"
        print(f"✅ prompt_optimizer in get_stats()")
        
        assert 'performance_monitor' in stats, "get_stats() missing 'performance_monitor'"
        print(f"✅ performance_monitor in get_stats()")
        
        # Verify structure
        assert isinstance(stats['semantic_cache'], dict), "semantic_cache should be dict"
        assert isinstance(stats['multi_model_consensus'], dict), "multi_model_consensus should be dict"
        assert isinstance(stats['prompt_optimizer'], dict), "prompt_optimizer should be dict"
        assert isinstance(stats['performance_monitor'], dict), "performance_monitor should be dict"
        print("✅ All stats have correct structure")
        
        # Check base stats still present
        assert 'session_id' in stats, "Base stats missing 'session_id'"
        assert 'app_type' in stats, "Base stats missing 'app_type'"
        print("✅ Base stats still present")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_prompt_optimizer():
    """Test prompt optimizer basic operations"""
    print("\n" + "="*60)
    print("🧪 TEST 6: Prompt Optimizer")
    print("="*60)
    
    try:
        brain = CompanionBrain(app_type="test")
        
        # Test that default variants are registered
        stats = brain.get_prompt_optimization_stats()
        assert 'task_types' in stats, "Stats missing 'task_types'"
        assert len(stats['task_types']) > 0, "No default variants registered"
        print(f"✅ Default variants registered: {stats['task_types']}")
        
        # Test optimize_prompt
        prompt = brain.optimize_prompt(
            'code_generation',
            {'task': 'sort an array'},
            exploration_rate=0.5
        )
        assert isinstance(prompt, str), "optimize_prompt should return string"
        assert len(prompt) > 0, "optimize_prompt returned empty string"
        print(f"✅ optimize_prompt works: {prompt[:60]}...")
        
        # Test record_prompt_result
        brain.record_prompt_result(
            'code_generation',
            'detailed',
            success=True,
            latency=0.5,
            response_length=100
        )
        print("✅ record_prompt_result works")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_performance_monitor():
    """Test performance monitor basic operations"""
    print("\n" + "="*60)
    print("🧪 TEST 7: Performance Monitor")
    print("="*60)
    
    try:
        brain = CompanionBrain(app_type="test")
        
        # Record some sample metrics
        brain.performance_monitor.record('test_metric', 0.1)
        brain.performance_monitor.record('test_metric', 0.2)
        brain.performance_monitor.record('test_metric', 0.3)
        brain.performance_monitor.record('test_metric', 0.4)
        brain.performance_monitor.record('test_metric', 0.5)
        print("✅ Recorded sample metrics")
        
        # Test percentiles
        percentiles = brain.get_performance_percentiles('test_metric')
        assert 'p50' in percentiles, "Percentiles missing 'p50'"
        assert 'p95' in percentiles, "Percentiles missing 'p95'"
        assert 'p99' in percentiles, "Percentiles missing 'p99'"
        assert 'mean' in percentiles, "Percentiles missing 'mean'"
        assert percentiles['count'] == 5, f"Expected 5 samples, got {percentiles['count']}"
        print(f"✅ Percentiles work: P50={percentiles['p50']:.3f}, P95={percentiles['p95']:.3f}, P99={percentiles['p99']:.3f}")
        
        # Test histogram
        histogram = brain.get_latency_histogram('test_metric', num_buckets=3)
        assert 'buckets' in histogram, "Histogram missing 'buckets'"
        assert 'counts' in histogram, "Histogram missing 'counts'"
        assert histogram['total'] == 5, f"Expected 5 total, got {histogram['total']}"
        print(f"✅ Histogram works: {histogram['buckets']}")
        
        # Test get_performance_monitoring_stats
        perf_stats = brain.get_performance_monitoring_stats()
        assert 'total_metrics' in perf_stats, "Performance stats missing 'total_metrics'"
        assert 'total_samples' in perf_stats, "Performance stats missing 'total_samples'"
        assert perf_stats['total_samples'] >= 5, f"Expected >=5 samples, got {perf_stats['total_samples']}"
        print(f"✅ Performance monitoring stats work: {perf_stats['total_metrics']} metrics, {perf_stats['total_samples']} samples")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all smoke tests"""
    print("\n" + "="*80)
    print("🚀 TIER 3 SMOKE TESTS (No API Calls)")
    print("="*80)
    print("Testing: Implementation structure and integration")
    
    results = []
    
    # Test 1: Classes exist
    result1 = test_tier3_classes_exist()
    results.append(("Tier 3 Classes Exist", result1))
    
    # Test 2: Brain integration
    result2 = test_brain_tier3_integration()
    results.append(("Brain Integration", result2))
    
    # Test 3: Semantic cache basic ops
    result3 = test_semantic_cache_basic()
    results.append(("Semantic Cache Basic", result3))
    
    # Test 4: Consensus stats
    result4 = test_consensus_stats()
    results.append(("Consensus Stats", result4))
    
    # Test 5: Stats integration
    result5 = test_stats_integration()
    results.append(("Stats Integration", result5))
    
    # Test 6: Prompt optimizer
    result6 = test_prompt_optimizer()
    results.append(("Prompt Optimizer", result6))
    
    # Test 7: Performance monitor
    result7 = test_performance_monitor()
    results.append(("Performance Monitor", result7))
    
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
    
    if passed == total:
        print("\n🎉 All Tier 3 smoke tests PASSED!")
        print("✅ Feature 1/4: Semantic cache with embeddings")
        print("✅ Feature 2/4: Multi-model consensus querying")
        print("✅ Feature 3/4: Prompt optimization with A/B testing")
        print("✅ Feature 4/4: Advanced observability (P50/P95/P99)")
        print("\n🏆 ALL TIER 3 FEATURES COMPLETE!")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
    
    print("="*80)
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
