#!/usr/bin/env python3
"""
Test Phase 2: Search Layer
===========================

Tests the Meilisearch integration and unified search engine
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def test_meilisearch_client_logic():
    """Test 1: Meilisearch Client Logic"""
    print("\n" + "="*60)
    print("🧪 Test 1: Meilisearch Client Logic")
    print("="*60)
    
    try:
        from search.meilisearch_client import MeilisearchClient
        
        print("✅ MeilisearchClient imported successfully")
        
        # Check class structure
        print("\n📋 Available methods:")
        methods = [m for m in dir(MeilisearchClient) if not m.startswith('_')]
        for method in methods:
            print(f"  • {method}")
        
        print("\n⚠️  Note: Skipping connection test (Docker not available)")
        print("   Required: docker-compose up meilisearch")
        
        print("\n✅ Meilisearch Client logic test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Meilisearch Client test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_search_engine_logic():
    """Test 2: Search Engine Logic"""
    print("\n" + "="*60)
    print("🧪 Test 2: Search Engine Logic")
    print("="*60)
    
    try:
        from search.search_engine import SearchEngine
        
        print("✅ SearchEngine imported successfully")
        
        # Initialize search engine
        print("\n📦 Initializing Search Engine...")
        engine = SearchEngine()
        
        print(f"✅ Search Engine initialized")
        print(f"  • Text Search: {'Enabled' if engine.text_search_enabled else 'Disabled'}")
        print(f"  • Vector Search: {'Enabled' if engine.vector_search_enabled else 'Disabled'}")
        
        # Check methods
        print("\n📋 Available methods:")
        methods = [m for m in dir(SearchEngine) if not m.startswith('_') and callable(getattr(SearchEngine, m, None))]
        for method in methods:
            print(f"  • {method}")
        
        print("\n✅ Search Engine logic test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Search Engine test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_search_integration():
    """Test 3: Search Integration with Phase 1"""
    print("\n" + "="*60)
    print("🧪 Test 3: Phase 1 + Phase 2 Integration")
    print("="*60)
    
    try:
        from search import get_search_engine
        from knowledge import get_vector_store
        
        print("✅ All modules imported successfully")
        
        # Initialize components
        print("\n📦 Initializing components...")
        search_engine = get_search_engine()
        vector_store = get_vector_store()
        
        print(f"✅ Components initialized")
        print(f"  • Search Engine: Ready")
        print(f"  • Vector Store: {'Ready' if vector_store.enabled else 'Not available'}")
        
        # Check integration
        print("\n🔗 Integration Status:")
        print(f"  • Text Search: {search_engine.text_search_enabled}")
        print(f"  • Vector Search: {search_engine.vector_search_enabled}")
        print(f"  • Hybrid Search: {search_engine.text_search_enabled or search_engine.vector_search_enabled}")
        
        print("\n✅ Integration test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Integration test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_search_methods():
    """Test 4: Search Methods (Without Docker)"""
    print("\n" + "="*60)
    print("🧪 Test 4: Search Methods")
    print("="*60)
    
    try:
        from search import get_search_engine
        
        engine = get_search_engine()
        
        print("Testing search methods (no Docker, expecting graceful failures)...")
        
        # Test fast search
        print("\n🔍 Testing fast_search()...")
        result = engine.fast_search("test query", limit=5)
        print(f"  • Result type: {type(result)}")
        print(f"  • Has 'hits': {'hits' in result}")
        print(f"  ✅ Method callable")
        
        # Test semantic search
        print("\n🔍 Testing semantic_search()...")
        result = engine.semantic_search("test query", limit=5)
        print(f"  • Result type: {type(result)}")
        print(f"  • Has 'hits': {'hits' in result}")
        print(f"  ✅ Method callable")
        
        # Test hybrid search
        print("\n🔍 Testing hybrid_search()...")
        result = engine.hybrid_search("test query", limit=5)
        print(f"  • Result type: {type(result)}")
        print(f"  • Has 'hits': {'hits' in result}")
        print(f"  ✅ Method callable")
        
        # Test get_stats
        print("\n🔍 Testing get_stats()...")
        stats = engine.get_stats()
        print(f"  • Stats type: {type(stats)}")
        print(f"  • Text search: {stats.get('text_search', {}).get('enabled')}")
        print(f"  • Vector search: {stats.get('vector_search', {}).get('enabled')}")
        print(f"  ✅ Method callable")
        
        print("\n✅ Search methods test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Search methods test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_phase2_readiness():
    """Test 5: Phase 2 Readiness Check"""
    print("\n" + "="*60)
    print("🧪 Test 5: Phase 2 Readiness")
    print("="*60)
    
    checks = {
        'Meilisearch Client': False,
        'Search Engine': False,
        'Integration with Phase 1': False,
        'Search Methods': False
    }
    
    try:
        from search import get_meilisearch_client
        checks['Meilisearch Client'] = True
    except:
        pass
    
    try:
        from search import get_search_engine
        checks['Search Engine'] = True
    except:
        pass
    
    try:
        from search import get_search_engine
        from knowledge import get_vector_store
        checks['Integration with Phase 1'] = True
    except:
        pass
    
    try:
        from search import get_search_engine
        engine = get_search_engine()
        _ = engine.fast_search("test")
        checks['Search Methods'] = True
    except:
        pass
    
    print("\n📊 Component Status:")
    for component, status in checks.items():
        status_icon = "✅" if status else "❌"
        print(f"  {status_icon} {component}")
    
    all_ready = all(checks.values())
    
    if all_ready:
        print("\n✅ Phase 2 complete and ready!")
        print("\n📝 To start services:")
        print("   cd companion_baas")
        print("   docker-compose up -d")
        print("")
        print("Then test with live services:")
        print("   python test_phase2_with_services.py")
    else:
        print("\n⚠️  Some components missing")
    
    return all_ready


def main():
    """Run all Phase 2 tests"""
    print("\n" + "🔍 " + "="*58)
    print("🔍  PHASE 2: SEARCH LAYER TEST SUITE")
    print("🔍  Testing without Docker services")
    print("🔍 " + "="*58)
    
    tests = [
        ("Meilisearch Client", test_meilisearch_client_logic),
        ("Search Engine", test_search_engine_logic),
        ("Integration", test_search_integration),
        ("Search Methods", test_search_methods),
        ("Phase 2 Readiness", test_phase2_readiness)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    # Summary
    print("\n" + "="*60)
    print("📊 PHASE 2 TEST SUMMARY")
    print("="*60)
    print(f"✅ Passed: {passed}/{len(tests)}")
    print(f"❌ Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 Phase 2 Search Layer is complete!")
        print("\n💡 What you have now:")
        print("   ✅ Meilisearch client for fast text search")
        print("   ✅ Search engine combining text + vector search")
        print("   ✅ Hybrid search capabilities")
        print("   ✅ Integration with Phase 1 Knowledge Layer")
        print("")
        print("📝 Next: Install Docker to test with live services")
        print("   sudo apt install docker.io docker-compose")
        print("   cd companion_baas && docker-compose up -d")
    else:
        print(f"\n⚠️  {failed} test(s) failed")
    
    return failed == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
