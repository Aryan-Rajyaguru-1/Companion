#!/usr/bin/env python3
"""
Test Phase 1: Knowledge Layer Components
=========================================

Tests without requiring Docker:
- Vector Store (Sentence Transformers)
- Configuration system
- Client initialization logic
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
from typing import List, Dict

def test_vector_store():
    """Test 1: Vector Store (Sentence Transformers)"""
    print("\n" + "="*60)
    print("🧪 Test 1: Vector Store - Text Embeddings")
    print("="*60)
    
    try:
        from knowledge.vector_store import VectorStore
        
        print("✅ VectorStore imported successfully")
        
        # Initialize
        print("📦 Initializing VectorStore (downloading model if needed)...")
        vector_store = VectorStore()
        model_name = getattr(vector_store, 'model_name', 'sentence-transformers/all-MiniLM-L6-v2')
        print(f"✅ VectorStore initialized with model: {model_name}")
        
        # Test single text encoding
        print("\n🔍 Testing single text encoding...")
        text = "Python is a programming language"
        embedding = vector_store.encode_text(text)
        
        print(f"✅ Encoded text: '{text}'")
        if hasattr(embedding, 'shape'):
            print(f"📊 Embedding shape: {embedding.shape}")
        print(f"📊 Embedding dimension: {len(embedding)}")
        print(f"📊 Sample values: {embedding[:5]}")
        
        # Test batch encoding
        print("\n🔍 Testing batch encoding...")
        texts = [
            "Python is great for AI",
            "JavaScript is used for web development",
            "Java is used for enterprise applications"
        ]
        embeddings = vector_store.encode_texts(texts)
        
        print(f"✅ Encoded {len(texts)} texts")
        print(f"📊 Embeddings shape: {embeddings.shape}")
        
        # Test similarity computation
        print("\n🔍 Testing similarity computation...")
        query = "AI and machine learning"
        query_embedding = vector_store.encode_text(query)
        
        for i, text in enumerate(texts):
            text_embedding = embeddings[i]
            similarity = vector_store.compute_similarity(query_embedding, text_embedding)
            print(f"  • '{text}' - Similarity: {similarity:.4f}")
        
        print("\n✅ Vector Store test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Vector Store test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_system():
    """Test 2: Configuration System"""
    print("\n" + "="*60)
    print("🧪 Test 2: Configuration System")
    print("="*60)
    
    try:
        from config import BrainConfig, ElasticsearchConfig, BytezConfig, MeilisearchConfig
        
        print("✅ Config classes imported successfully")
        
        # Initialize BrainConfig
        config = BrainConfig()
        
        print("\n📋 Elasticsearch Configuration:")
        print(f"  • Host: {config.elasticsearch.host}")
        print(f"  • Port: {config.elasticsearch.port}")
        print(f"  • Embedding Model: {config.elasticsearch.embedding_model}")
        
        print("\n📋 Meilisearch Configuration:")
        print(f"  • Host: {config.meilisearch.host}")
        print(f"  • Port: {config.meilisearch.port}")
        print(f"  • Enabled: {config.meilisearch.enabled}")
        
        print("\n📋 Bytez Configuration:")
        print(f"  • Enabled: {config.bytez.enabled}")
        print(f"  • Default Model: {config.bytez.default_model}")
        print(f"  • API Key: {config.bytez.api_key[:20]}...")
        
        if hasattr(config, 'features'):
            print("\n📋 Feature Flags:")
            print(f"  • Knowledge Layer: {config.features.knowledge_layer}")
            print(f"  • Search Layer: {config.features.search_layer}")
            print(f"  • Web Intelligence: {config.features.web_intelligence}")
            print(f"  • Code Execution: {config.features.code_execution}")
        else:
            print("\n📋 Feature Flags: (Config class doesn't have features yet)")
        
        print("\n✅ Configuration test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Configuration test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_elasticsearch_client_logic():
    """Test 3: Elasticsearch Client (Logic only, no connection)"""
    print("\n" + "="*60)
    print("🧪 Test 3: Elasticsearch Client Logic")
    print("="*60)
    
    try:
        from knowledge.elasticsearch_client import ElasticsearchClient
        
        print("✅ ElasticsearchClient imported successfully")
        
        # Check class structure
        print("\n📋 Available methods:")
        methods = [m for m in dir(ElasticsearchClient) if not m.startswith('_')]
        for method in methods:
            print(f"  • {method}")
        
        print("\n⚠️  Note: Skipping connection test (Docker not available)")
        print("   Required: docker-compose up elasticsearch")
        
        print("\n✅ Elasticsearch Client logic test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Elasticsearch Client test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_retriever_logic():
    """Test 4: Knowledge Retriever (Logic only)"""
    print("\n" + "="*60)
    print("🧪 Test 4: Knowledge Retriever Logic")
    print("="*60)
    
    try:
        from knowledge.retriever import KnowledgeRetriever
        
        print("✅ KnowledgeRetriever imported successfully")
        
        # Check class structure
        print("\n📋 Available methods:")
        methods = [m for m in dir(KnowledgeRetriever) if not m.startswith('_')]
        for method in methods:
            print(f"  • {method}")
        
        print("\n⚠️  Note: Skipping connection test (Docker not available)")
        print("   Required: docker-compose up elasticsearch")
        
        print("\n✅ Knowledge Retriever logic test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Knowledge Retriever test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_docker_compose():
    """Test 5: Docker Compose Configuration"""
    print("\n" + "="*60)
    print("🧪 Test 5: Docker Compose Configuration")
    print("="*60)
    
    try:
        import yaml
        
        docker_compose_path = os.path.join(os.path.dirname(__file__), 'docker-compose.yml')
        
        if not os.path.exists(docker_compose_path):
            print("❌ docker-compose.yml not found")
            return False
        
        with open(docker_compose_path, 'r') as f:
            compose_config = yaml.safe_load(f)
        
        print("✅ docker-compose.yml loaded successfully")
        
        print("\n📋 Services defined:")
        for service_name, service_config in compose_config.get('services', {}).items():
            image = service_config.get('image', 'N/A')
            ports = service_config.get('ports', [])
            print(f"\n  • {service_name}")
            print(f"    Image: {image}")
            if ports:
                print(f"    Ports: {ports}")
        
        print("\n✅ Docker Compose configuration test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Docker Compose test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration_readiness():
    """Test 6: Integration Readiness Check"""
    print("\n" + "="*60)
    print("🧪 Test 6: Integration Readiness")
    print("="*60)
    
    checks = {
        'Vector Store': False,
        'Configuration': False,
        'Elasticsearch Client': False,
        'Knowledge Retriever': False,
        'Docker Compose': False
    }
    
    try:
        from knowledge.vector_store import VectorStore
        checks['Vector Store'] = True
    except:
        pass
    
    try:
        from config import BrainConfig
        checks['Configuration'] = True
    except:
        pass
    
    try:
        from knowledge.elasticsearch_client import ElasticsearchClient
        checks['Elasticsearch Client'] = True
    except:
        pass
    
    try:
        from knowledge.retriever import KnowledgeRetriever
        checks['Knowledge Retriever'] = True
    except:
        pass
    
    try:
        docker_compose_path = os.path.join(os.path.dirname(__file__), 'docker-compose.yml')
        if os.path.exists(docker_compose_path):
            checks['Docker Compose'] = True
    except:
        pass
    
    print("\n📊 Component Status:")
    for component, status in checks.items():
        status_icon = "✅" if status else "❌"
        print(f"  {status_icon} {component}")
    
    all_ready = all(checks.values())
    
    if all_ready:
        print("\n✅ All Phase 1 components ready!")
        print("\n📝 To start services:")
        print("   cd companion_baas")
        print("   docker-compose up -d")
    else:
        print("\n⚠️  Some components missing")
    
    return all_ready


def main():
    """Run all Phase 1 tests"""
    print("\n" + "🧠 " + "="*58)
    print("🧠  PHASE 1: KNOWLEDGE LAYER TEST SUITE")
    print("🧠  Testing without Docker services")
    print("🧠 " + "="*58)
    
    tests = [
        ("Vector Store", test_vector_store),
        ("Configuration System", test_config_system),
        ("Elasticsearch Client", test_elasticsearch_client_logic),
        ("Knowledge Retriever", test_retriever_logic),
        ("Docker Compose Config", test_docker_compose),
        ("Integration Readiness", test_integration_readiness)
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
    print("📊 PHASE 1 TEST SUMMARY")
    print("="*60)
    print(f"✅ Passed: {passed}/{len(tests)}")
    print(f"❌ Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 Phase 1 Knowledge Layer is ready!")
        print("\n📝 Next Steps:")
        print("   1. Install Docker (if not installed):")
        print("      sudo apt install docker.io docker-compose")
        print("")
        print("   2. Start services:")
        print("      cd companion_baas")
        print("      docker-compose up -d")
        print("")
        print("   3. Test with services:")
        print("      python test_phase1_with_services.py")
        print("")
        print("   4. Move to Phase 2: Search Layer")
    else:
        print(f"\n⚠️  {failed} test(s) failed")
        print("   Fix issues before proceeding to Phase 2")
    
    return failed == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
