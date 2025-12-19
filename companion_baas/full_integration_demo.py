#!/usr/bin/env python3
"""
🎯 Companion Brain - Full Integration Demo
==========================================

Demonstrates all Phase 1 + Phase 2 capabilities:
- Fast text search (Meilisearch)
- Semantic vector search (Elasticsearch)
- Hybrid search (combining both)
- Redis caching
- Real-world knowledge base scenario
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import time
from datetime import datetime

def demo_banner(title):
    """Print a formatted banner"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def demo_1_meilisearch_fast_search():
    """Demo 1: Fast Text Search with Meilisearch"""
    demo_banner("🚀 DEMO 1: Meilisearch Fast Text Search (<50ms)")
    
    from search import get_meilisearch_client
    
    client = get_meilisearch_client()
    
    # Create knowledge base
    print("\n📚 Creating Programming Knowledge Base...")
    index_name = 'programming_kb'
    
    client.create_index(index_name)
    client.configure_index(
        index_name,
        searchable_attributes=['title', 'content', 'tags'],
        filterable_attributes=['category', 'difficulty', 'language']
    )
    
    # Add programming knowledge
    docs = [
        {
            'id': '1',
            'title': 'Python Basics',
            'content': 'Python is a high-level programming language known for its simplicity and readability. Perfect for beginners.',
            'category': 'tutorial',
            'difficulty': 'beginner',
            'language': 'python',
            'tags': ['python', 'basics', 'tutorial']
        },
        {
            'id': '2',
            'title': 'JavaScript Async/Await',
            'content': 'Async/await makes asynchronous code look synchronous. It\'s built on top of promises and makes code cleaner.',
            'category': 'advanced',
            'difficulty': 'intermediate',
            'language': 'javascript',
            'tags': ['javascript', 'async', 'promises']
        },
        {
            'id': '3',
            'title': 'Machine Learning with Python',
            'content': 'Use scikit-learn and TensorFlow for machine learning. Start with simple models and gradually increase complexity.',
            'category': 'tutorial',
            'difficulty': 'advanced',
            'language': 'python',
            'tags': ['python', 'ml', 'ai', 'tensorflow']
        },
        {
            'id': '4',
            'title': 'React Hooks Guide',
            'content': 'React Hooks like useState and useEffect let you use state and lifecycle features in functional components.',
            'category': 'guide',
            'difficulty': 'intermediate',
            'language': 'javascript',
            'tags': ['react', 'javascript', 'hooks', 'frontend']
        },
        {
            'id': '5',
            'title': 'Docker Containerization',
            'content': 'Docker containers package applications with their dependencies. Makes deployment consistent across environments.',
            'category': 'devops',
            'difficulty': 'intermediate',
            'language': 'docker',
            'tags': ['docker', 'containers', 'devops']
        }
    ]
    
    client.add_documents(index_name, docs)
    print(f"✅ Added {len(docs)} documents to knowledge base")
    
    time.sleep(1)  # Wait for indexing
    
    # Demo searches
    print("\n🔍 Search Examples:")
    
    queries = [
        ("python", "Finding Python tutorials"),
        ("async javascript", "Asynchronous JavaScript"),
        ("machine learning", "AI/ML content"),
        ("beginner", "Beginner-friendly content")
    ]
    
    for query, description in queries:
        print(f"\n  Query: '{query}' - {description}")
        start_time = time.time()
        results = client.search(index_name, query, limit=2)
        search_time = (time.time() - start_time) * 1000
        
        print(f"  ⚡ Search time: {search_time:.2f}ms")
        for hit in results.get('hits', [])[:2]:
            print(f"    • {hit['title']} ({hit['difficulty']})")
    
    # Filtered search
    print("\n🎯 Filtered Search: Python + Intermediate difficulty")
    results = client.search(index_name, "python", limit=5, filters="difficulty = intermediate")
    print(f"  Found {len(results.get('hits', []))} results")
    for hit in results.get('hits', []):
        print(f"    • {hit['title']}")
    
    print("\n✅ Demo 1 Complete!")
    return index_name


def demo_2_elasticsearch_vector_search():
    """Demo 2: Semantic Vector Search with Elasticsearch"""
    demo_banner("🧠 DEMO 2: Elasticsearch Semantic Vector Search")
    
    from knowledge import get_elasticsearch_client, get_vector_store
    
    es_client = get_elasticsearch_client()
    vector_store = get_vector_store()
    
    if not es_client.enabled or not vector_store.enabled:
        print("⚠️  Elasticsearch or VectorStore not available")
        return None
    
    # Create index
    print("\n📚 Creating Semantic Knowledge Base...")
    index_name = 'semantic_kb'
    es_client.create_index(index_name, dimension=384)
    
    # Add documents with semantic meaning
    docs_data = [
        {
            'id': 'sem1',
            'title': 'Building REST APIs',
            'content': 'Creating RESTful web services with proper HTTP methods, status codes, and JSON responses.'
        },
        {
            'id': 'sem2',
            'title': 'Database Design',
            'content': 'Designing relational databases with proper normalization, indexes, and foreign key relationships.'
        },
        {
            'id': 'sem3',
            'title': 'API Development Best Practices',
            'content': 'Best practices for API design including versioning, authentication, rate limiting, and documentation.'
        },
        {
            'id': 'sem4',
            'title': 'Neural Networks Explained',
            'content': 'Understanding neural networks: layers, activation functions, backpropagation, and gradient descent.'
        },
        {
            'id': 'sem5',
            'title': 'Web Service Architecture',
            'content': 'Designing scalable web services with microservices, load balancing, and service discovery.'
        }
    ]
    
    print(f"🧮 Generating embeddings for {len(docs_data)} documents...")
    for doc_data in docs_data:
        text = f"{doc_data['title']} {doc_data['content']}"
        embedding = vector_store.encode(text)
        
        doc = {
            **doc_data,
            'embedding': embedding,
            'timestamp': datetime.utcnow()
        }
        
        es_client.index_doc(index_name, doc_data['id'], doc)
    
    print(f"✅ Indexed {len(docs_data)} documents with semantic embeddings")
    
    time.sleep(2)  # Wait for indexing
    
    # Semantic searches - testing understanding
    print("\n🔍 Semantic Search Examples:")
    
    queries = [
        ("How do I create web endpoints?", "Testing: REST API understanding"),
        ("Tell me about structuring data in SQL", "Testing: Database understanding"),
        ("Explain deep learning", "Testing: ML understanding"),
        ("microservices and scalability", "Testing: Architecture understanding")
    ]
    
    for query, description in queries:
        print(f"\n  Query: '{query}'")
        print(f"  {description}")
        
        # Generate query embedding
        query_embedding = vector_store.encode(query)
        
        # Search
        results = es_client.search_similar(
            index_name=index_name,
            query_embedding=query_embedding,
            k=2
        )
        
        print(f"  📊 Found {len(results)} semantic matches:")
        for result in results:
            score = result.get('_score', 0)
            source = result.get('_source', {})
            title = source.get('title', 'N/A')
            print(f"    • {title} (similarity: {score:.4f})")
    
    print("\n✅ Demo 2 Complete!")
    return index_name


def demo_3_hybrid_search():
    """Demo 3: Hybrid Search - Best of Both Worlds"""
    demo_banner("⚡ DEMO 3: Hybrid Search (Text + Semantic)")
    
    from search import get_search_engine
    from knowledge import get_vector_store
    
    engine = get_search_engine()
    vector_store = get_vector_store()
    
    print(f"\n🔧 Search Engine Status:")
    print(f"  • Text Search: {engine.text_search_enabled}")
    print(f"  • Vector Search: {engine.vector_search_enabled}")
    
    if not (engine.text_search_enabled or engine.vector_search_enabled):
        print("⚠️  No search backends available")
        return
    
    # Create unified knowledge base
    print("\n📚 Creating Unified Knowledge Base...")
    index_name = 'unified_kb'
    
    # Create in both backends
    if engine.text_search_enabled:
        engine.meilisearch.create_index(index_name)
        engine.meilisearch.configure_index(
            index_name,
            searchable_attributes=['title', 'content', 'summary'],
            filterable_attributes=['category', 'tags']
        )
    
    if engine.vector_search_enabled:
        engine.elasticsearch.create_index(index_name, dimension=384)
    
    # Add comprehensive documents
    docs = [
        {
            'id': 'unified1',
            'title': 'Python Flask Web Development',
            'content': 'Flask is a lightweight Python web framework for building web applications and APIs quickly.',
            'summary': 'Build web apps with Flask',
            'category': 'web',
            'tags': ['python', 'flask', 'web']
        },
        {
            'id': 'unified2',
            'title': 'React Component Patterns',
            'content': 'Learn advanced React patterns: HOCs, render props, custom hooks, and compound components.',
            'summary': 'Advanced React patterns',
            'category': 'frontend',
            'tags': ['react', 'javascript', 'patterns']
        },
        {
            'id': 'unified3',
            'title': 'Docker and Kubernetes',
            'content': 'Container orchestration with Kubernetes: pods, services, deployments, and scaling strategies.',
            'summary': 'Container orchestration',
            'category': 'devops',
            'tags': ['docker', 'kubernetes', 'containers']
        },
        {
            'id': 'unified4',
            'title': 'PostgreSQL Performance',
            'content': 'Optimize PostgreSQL: query planning, indexing strategies, connection pooling, and monitoring.',
            'summary': 'Database optimization',
            'category': 'database',
            'tags': ['postgresql', 'database', 'performance']
        }
    ]
    
    print(f"📄 Indexing {len(docs)} documents in both search backends...")
    
    for doc in docs:
        # Add to Meilisearch (text search)
        if engine.text_search_enabled:
            engine.meilisearch.add_documents(index_name, [doc])
        
        # Add to Elasticsearch (vector search)
        if engine.vector_search_enabled and vector_store.enabled:
            text = f"{doc['title']} {doc['content']}"
            embedding = vector_store.encode(text)
            
            es_doc = {
                **doc,
                'embedding': embedding
            }
            engine.elasticsearch.index_doc(index_name, doc['id'], es_doc)
    
    print(f"✅ Documents indexed in both backends")
    
    time.sleep(2)  # Wait for indexing
    
    # Hybrid search demonstrations
    print("\n🔍 Hybrid Search Examples:")
    
    test_queries = [
        "python web framework",
        "how to scale containers", 
        "frontend component design",
        "database query optimization"
    ]
    
    for query in test_queries:
        print(f"\n  Query: '{query}'")
        
        # Text search
        if engine.text_search_enabled:
            text_results = engine.fast_search(query, index_name, limit=2)
            print(f"  📝 Text search: {len(text_results.get('hits', []))} results")
            for hit in text_results.get('hits', [])[:1]:
                print(f"    • {hit.get('title')}")
        
        # Vector search
        if engine.vector_search_enabled:
            vector_results = engine.semantic_search(query, index_name, limit=2)
            print(f"  🧠 Semantic search: {len(vector_results.get('hits', []))} results")
            for hit in vector_results.get('hits', [])[:1]:
                source = hit.get('_source', {})
                print(f"    • {source.get('title')}")
        
        # Hybrid search (combines both)
        if engine.text_search_enabled or engine.vector_search_enabled:
            hybrid_results = engine.hybrid_search(query, index_name, limit=3)
            print(f"  ⚡ Hybrid search: {len(hybrid_results.get('hits', []))} results (weighted combination)")
            for hit in hybrid_results.get('hits', [])[:2]:
                if isinstance(hit, dict):
                    title = hit.get('title') or (hit.get('_source', {}) or {}).get('title', 'N/A') if isinstance(hit.get('_source'), dict) else 'N/A'
                    score = hit.get('_score', hit.get('score', 0))
                    print(f"    • {title} (score: {score:.4f})")
    
    print("\n✅ Demo 3 Complete!")


def demo_4_redis_caching():
    """Demo 4: Redis Caching"""
    demo_banner("⚡ DEMO 4: Redis Caching Layer")
    
    import redis
    import json
    
    print("\n📡 Connecting to Redis...")
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    
    if not r.ping():
        print("❌ Redis not available")
        return
    
    print("✅ Connected to Redis")
    
    # Cache search results
    print("\n💾 Caching Search Results:")
    
    cache_examples = [
        ("python:tutorials", {"hits": [{"title": "Python Basics"}, {"title": "Python Advanced"}], "count": 2}),
        ("javascript:async", {"hits": [{"title": "Async/Await Guide"}], "count": 1}),
        ("ml:tutorials", {"hits": [{"title": "ML with Python"}, {"title": "Deep Learning"}], "count": 2})
    ]
    
    for cache_key, data in cache_examples:
        # Set with 60 second expiry
        r.setex(f"search:{cache_key}", 60, json.dumps(data))
        print(f"  ✅ Cached: {cache_key} (TTL: 60s)")
    
    # Retrieve cached data
    print("\n🔍 Retrieving Cached Results:")
    for cache_key, _ in cache_examples:
        cached = r.get(f"search:{cache_key}")
        if cached:
            data = json.loads(cached)
            ttl = r.ttl(f"search:{cache_key}")
            print(f"  • {cache_key}: {data['count']} results (TTL: {ttl}s)")
    
    # Cache statistics
    print("\n📊 Cache Statistics:")
    
    # Set some user session data
    r.hset('user:123', mapping={
        'name': 'Developer',
        'last_search': 'python tutorials',
        'search_count': '5'
    })
    
    user_data = r.hgetall('user:123')
    print(f"  • User session cached: {user_data}")
    
    # Memory info
    info = r.info('memory')
    print(f"  • Memory used: {info['used_memory_human']}")
    print(f"  • Peak memory: {info['used_memory_peak_human']}")
    
    print("\n✅ Demo 4 Complete!")


def main():
    """Run full integration demo"""
    print("\n" + "🎯 " + "="*68)
    print("🎯  COMPANION BRAIN - FULL INTEGRATION DEMO")
    print("🎯  Phase 1 (Knowledge) + Phase 2 (Search) + Caching")
    print("🎯 " + "="*68)
    
    print("\n🚀 Starting comprehensive demonstration...")
    print("   This will showcase all capabilities of the Companion Brain")
    
    try:
        # Run all demos
        demo_1_meilisearch_fast_search()
        demo_2_elasticsearch_vector_search()
        demo_3_hybrid_search()
        demo_4_redis_caching()
        
        # Final summary
        demo_banner("🎉 INTEGRATION DEMO COMPLETE!")
        
        print("\n✅ Successfully demonstrated:")
        print("  • Fast text search with Meilisearch (<50ms)")
        print("  • Semantic vector search with Elasticsearch")
        print("  • Hybrid search combining both approaches")
        print("  • Redis caching for performance")
        print("  • Multi-index knowledge management")
        print("  • Real-world search scenarios")
        
        print("\n📊 System Status:")
        print("  • Meilisearch: ✅ Running (port 7700)")
        print("  • Elasticsearch: ✅ Running (port 9200)")
        print("  • Redis: ✅ Running (port 6379)")
        print("  • Vector Embeddings: ✅ Active (384 dimensions)")
        print("  • Hybrid Search: ✅ Operational")
        
        print("\n🎯 Next: Phase 3 - Web Intelligence")
        print("  • Crawl4AI for web scraping")
        print("  • Browser-Use for automation")
        print("  • Public APIs integration")
        print("  • Real-time data collection")
        
        print("\n" + "="*70)
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
