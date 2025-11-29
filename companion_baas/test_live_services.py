#!/usr/bin/env python3
"""
Test Live Services Integration
================================

Tests Phase 1 + Phase 2 with live Docker services
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def test_live_meilisearch():
    """Test 1: Live Meilisearch Connection"""
    print("\n" + "="*60)
    print("🧪 Test 1: Live Meilisearch")
    print("="*60)
    
    try:
        from search import get_meilisearch_client
        
        client = get_meilisearch_client()
        
        # Test connection
        print("📡 Testing connection...")
        health = client.client.health()
        print(f"✅ Meilisearch: {health.get('status', 'unknown')}")
        
        # Create test index
        print("\n📝 Creating test index...")
        client.create_index('test_docs')
        client.configure_index('test_docs', 
                              searchable_attributes=['title', 'content'],
                              filterable_attributes=['category'])
        print("✅ Index created and configured")
        
        # Add test documents
        print("\n📄 Adding test documents...")
        docs = [
            {
                'id': 'doc1',
                'title': 'Introduction to AI',
                'content': 'Artificial Intelligence is transforming the world',
                'category': 'AI'
            },
            {
                'id': 'doc2',
                'title': 'Machine Learning Basics',
                'content': 'Learn the fundamentals of machine learning',
                'category': 'ML'
            },
            {
                'id': 'doc3',
                'title': 'Deep Learning Guide',
                'content': 'Neural networks and deep learning explained',
                'category': 'DL'
            }
        ]
        client.add_documents('test_docs', docs)
        print(f"✅ Added {len(docs)} documents")
        
        # Wait for indexing
        import time
        time.sleep(1)
        
        # Test search
        print("\n🔍 Testing search...")
        results = client.search('test_docs', 'learning', limit=5)
        print(f"✅ Found {len(results.get('hits', []))} results for 'learning'")
        for hit in results.get('hits', []):
            print(f"  • {hit.get('title')} (score: {hit.get('_rankingScore', 0):.2f})")
        
        # Get stats
        print("\n📊 Getting index stats...")
        stats = client.get_stats('test_docs')
        num_docs = getattr(stats, 'number_of_documents', 0) if hasattr(stats, 'number_of_documents') else 0
        print(f"✅ Index has {num_docs} documents")
        
        print("\n✅ Live Meilisearch test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Live Meilisearch test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_live_elasticsearch():
    """Test 2: Live Elasticsearch Connection"""
    print("\n" + "="*60)
    print("🧪 Test 2: Live Elasticsearch")
    print("="*60)
    
    try:
        from knowledge import get_elasticsearch_client, get_vector_store
        
        es_client = get_elasticsearch_client()
        vector_store = get_vector_store()
        
        # Test connection
        print("📡 Testing connection...")
        try:
            if es_client.enabled and es_client.client and es_client.client.ping():
                print("✅ Elasticsearch: connected")
            else:
                print("⚠️  Elasticsearch: not reachable or not enabled")
                return False
        except Exception as e:
            print(f"⚠️  Elasticsearch connection issue: {e}")
            return False
        
        # Create test index
        print("\n📝 Creating test index...")
        index_name = 'test_vectors'
        es_client.create_index(index_name, dimension=384)
        print("✅ Vector index created")
        
        # Test embeddings
        print("\n🧮 Generating embeddings...")
        text = "This is a test document about artificial intelligence"
        embedding = vector_store.encode(text)
        print(f"✅ Generated embedding: {len(embedding)} dimensions")
        
        # Index document with vector
        print("\n📄 Indexing document with vector...")
        doc = {
            'text': text,
            'category': 'test',
            'embedding': embedding.tolist() if hasattr(embedding, 'tolist') else embedding
        }
        es_client.index_doc(index_name, 'doc1', doc)
        print("✅ Document indexed")
        
        # Wait for indexing
        import time
        time.sleep(1)
        
        # Test vector search
        print("\n🔍 Testing vector search...")
        query_text = "tell me about AI"
        query_vector = vector_store.encode(query_text)
        results = es_client.search_similar(index_name, query_vector, k=3)
        
        print(f"✅ Found {len(results)} results")
        for i, hit in enumerate(results, 1):
            score = hit.get('_score', 0)
            text = hit.get('_source', {}).get('text', '')
            print(f"  {i}. Score: {score:.4f}")
            print(f"     Text: {text[:60]}...")
        
        print("\n✅ Live Elasticsearch test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Live Elasticsearch test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_live_hybrid_search():
    """Test 3: Live Hybrid Search"""
    print("\n" + "="*60)
    print("🧪 Test 3: Live Hybrid Search")
    print("="*60)
    
    try:
        from search import get_search_engine
        
        engine = get_search_engine()
        
        print("📊 Search Engine Status:")
        print(f"  • Text Search: {engine.text_search_enabled}")
        print(f"  • Vector Search: {engine.vector_search_enabled}")
        
        # Create indexes
        print("\n📝 Setting up indexes...")
        
        # Meilisearch index
        if engine.text_search_enabled:
            engine.meilisearch.create_index('knowledge_base')
            engine.meilisearch.configure_index(
                'knowledge_base',
                searchable_attributes=['title', 'content', 'summary'],
                filterable_attributes=['category', 'tags']
            )
            print("✅ Meilisearch index ready")
        
        # Elasticsearch index
        if engine.vector_search_enabled:
            engine.elasticsearch.create_index('knowledge_base', dimension=384)
            print("✅ Elasticsearch index ready")
        
        # Index sample documents
        print("\n📄 Indexing sample documents...")
        docs = [
            {
                'id': 'kb1',
                'title': 'Python Programming',
                'content': 'Python is a high-level programming language known for its simplicity',
                'summary': 'Learn Python basics',
                'category': 'Programming',
                'tags': ['python', 'coding']
            },
            {
                'id': 'kb2',
                'title': 'JavaScript Guide',
                'content': 'JavaScript is the language of the web, enabling interactive websites',
                'summary': 'Web development with JS',
                'category': 'Programming',
                'tags': ['javascript', 'web']
            },
            {
                'id': 'kb3',
                'title': 'AI and Machine Learning',
                'content': 'Artificial Intelligence uses algorithms to learn from data and make predictions',
                'summary': 'Understanding AI/ML',
                'category': 'AI',
                'tags': ['ai', 'ml', 'data']
            }
        ]
        
        for doc in docs:
            engine.index_document('knowledge_base', doc['id'], doc)
        
        print(f"✅ Indexed {len(docs)} documents")
        
        # Wait for indexing
        import time
        time.sleep(2)
        
        # Test different search types
        print("\n🔍 Testing search methods...")
        
        # Fast text search
        if engine.text_search_enabled:
            print("\n1️⃣  Fast Text Search: 'programming'")
            results = engine.fast_search('programming', limit=3)
            print(f"   Found {len(results.get('hits', []))} results")
            for hit in results.get('hits', [])[:2]:
                print(f"   • {hit.get('title')}")
        
        # Semantic search
        if engine.vector_search_enabled:
            print("\n2️⃣  Semantic Vector Search: 'coding tutorials'")
            results = engine.semantic_search('coding tutorials', limit=3)
            print(f"   Found {len(results.get('hits', []))} results")
            for hit in results.get('hits', [])[:2]:
                text = hit.get('_source', {}).get('title', 'N/A')
                print(f"   • {text}")
        
        # Hybrid search
        if engine.text_search_enabled or engine.vector_search_enabled:
            print("\n3️⃣  Hybrid Search: 'machine learning'")
            results = engine.hybrid_search('machine learning', limit=3)
            print(f"   Found {len(results.get('hits', []))} results")
            for hit in results.get('hits', [])[:2]:
                title = hit.get('title') or hit.get('_source', {}).get('title', 'N/A')
                score = hit.get('score', 0)
                print(f"   • {title} (score: {score:.4f})")
        
        # Get stats
        print("\n📊 Getting search statistics...")
        stats = engine.get_stats()
        print(f"✅ Stats retrieved:")
        print(f"   Text Search: {stats.get('text_search', {}).get('enabled')}")
        print(f"   Vector Search: {stats.get('vector_search', {}).get('enabled')}")
        
        print("\n✅ Live Hybrid Search test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Live Hybrid Search test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_live_redis():
    """Test 4: Live Redis Cache"""
    print("\n" + "="*60)
    print("🧪 Test 4: Live Redis Cache")
    print("="*60)
    
    try:
        import redis
        
        # Connect to Redis
        print("📡 Connecting to Redis...")
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        
        # Test ping
        if r.ping():
            print("✅ Redis: connected")
        else:
            print("❌ Redis: not reachable")
            return False
        
        # Test set/get
        print("\n💾 Testing cache operations...")
        r.set('test_key', 'test_value')
        value = r.get('test_key')
        print(f"✅ Set/Get: '{value}'")
        
        # Test with expiry
        r.setex('temp_key', 60, 'expires in 60s')
        ttl = r.ttl('temp_key')
        print(f"✅ TTL: {ttl} seconds")
        
        # Test hash
        r.hset('user:1', mapping={'name': 'John', 'age': '30'})
        user = r.hgetall('user:1')
        print(f"✅ Hash: {user}")
        
        # Get info
        info = r.info('memory')
        used_memory = info.get('used_memory_human', 'N/A')
        print(f"\n📊 Redis Memory: {used_memory}")
        
        print("\n✅ Live Redis test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Live Redis test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all live service tests"""
    print("\n" + "🚀 " + "="*58)
    print("🚀  LIVE SERVICES INTEGRATION TEST")
    print("🚀  Phase 1 + Phase 2 with Docker")
    print("🚀 " + "="*58)
    
    tests = [
        ("Meilisearch", test_live_meilisearch),
        ("Elasticsearch", test_live_elasticsearch),
        ("Hybrid Search", test_live_hybrid_search),
        ("Redis Cache", test_live_redis)
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
    print("📊 LIVE SERVICES TEST SUMMARY")
    print("="*60)
    print(f"✅ Passed: {passed}/{len(tests)}")
    print(f"❌ Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 All services working perfectly!")
        print("\n💡 What's running:")
        print("   ✅ Meilisearch (port 7700) - Fast text search")
        print("   ✅ Elasticsearch (port 9200) - Vector search")
        print("   ✅ Redis (port 6379) - Caching layer")
        print("   ✅ Hybrid Search Engine - Best of both worlds")
        print("")
        print("📝 Next Steps:")
        print("   • Move to Phase 3: Web Intelligence")
        print("   • Integrate Crawl4AI, Browser-Use, Public APIs")
        print("   • Add web scraping and data collection")
    else:
        print(f"\n⚠️  {failed} test(s) failed")
        print("   Check Docker containers: sudo docker ps")
        print("   Check logs: sudo docker logs companion_elasticsearch")
    
    return failed == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
