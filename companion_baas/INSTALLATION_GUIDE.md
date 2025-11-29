# 🚀 Companion Brain - Installation & Setup Guide

> **Complete guide to set up the enhanced Companion Brain with Knowledge Layer**

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Detailed Setup](#detailed-setup)
4. [Testing](#testing)
5. [Troubleshooting](#troubleshooting)

---

## ✅ Prerequisites

### System Requirements
- **OS**: Linux, macOS, or Windows (with WSL2)
- **RAM**: 8GB minimum (16GB recommended)
- **Disk**: 5GB free space
- **Python**: 3.8 or higher
- **Docker**: Latest version (for services)

### Check Your System
```bash
# Check Python version
python --version  # Should be 3.8+

# Check Docker
docker --version
docker-compose --version

# Check available RAM
free -h  # Linux
vm_stat  # macOS
```

---

## 🚀 Quick Start

### Option 1: Docker Setup (Recommended)

```bash
# 1. Navigate to companion_baas directory
cd "Companion deepthink/companion_baas"

# 2. Start all services
docker-compose up -d

# 3. Wait for services to be healthy (30-60 seconds)
docker-compose ps

# 4. Install Python dependencies
pip install elasticsearch sentence-transformers meilisearch redis

# 5. Test the installation
python -c "from knowledge import get_knowledge_retriever; kr = get_knowledge_retriever(); print('✅ Knowledge Layer Ready!' if kr.is_enabled() else '❌ Check setup')"
```

### Option 2: Manual Installation

If you prefer not to use Docker:

```bash
# Install Elasticsearch
# See: https://www.elastic.co/guide/en/elasticsearch/reference/current/install-elasticsearch.html

# Install Meilisearch
# See: https://www.meilisearch.com/docs/learn/getting_started/installation

# Install Redis
# See: https://redis.io/docs/getting-started/installation/

# Install Python dependencies
pip install -r requirements.txt
```

---

## 🔧 Detailed Setup

### Step 1: Start Docker Services

```bash
cd companion_baas
docker-compose up -d
```

**What this does:**
- Starts Elasticsearch on port 9200
- Starts Meilisearch on port 7700
- Starts Redis on port 6379

**Verify services are running:**
```bash
# Check all services
docker-compose ps

# Expected output:
# NAME                          STATUS    PORTS
# companion_elasticsearch       Up        0.0.0.0:9200->9200/tcp
# companion_meilisearch         Up        0.0.0.0:7700->7700/tcp
# companion_redis               Up        0.0.0.0:6379->6379/tcp

# Test Elasticsearch
curl http://localhost:9200
# Should return: {"name":"...", "cluster_name":"..."}

# Test Meilisearch
curl http://localhost:7700/health
# Should return: {"status":"available"}

# Test Redis
redis-cli ping
# Should return: PONG
```

### Step 2: Install Python Dependencies

```bash
# Install core dependencies
pip install elasticsearch>=8.11.0
pip install sentence-transformers>=2.2.2
pip install meilisearch>=0.31.0
pip install redis>=5.0.0

# Download embedding model (first time only, ~90MB)
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
```

### Step 3: Verify Installation

Create a test script `test_knowledge_layer.py`:

```python
"""Test Knowledge Layer Installation"""

from companion_baas.knowledge import get_knowledge_retriever
from companion_baas.config import get_config

def test_installation():
    print("🧪 Testing Knowledge Layer Installation\n")
    
    # 1. Check configuration
    print("1️⃣ Checking configuration...")
    config = get_config()
    print(f"   ✅ Config loaded")
    print(f"   - Elasticsearch: {config.elasticsearch.host}:{config.elasticsearch.port}")
    print(f"   - Meilisearch: {config.meilisearch.host}:{config.meilisearch.port}")
    print(f"   - Redis: {config.redis.host}:{config.redis.port}\n")
    
    # 2. Initialize retriever
    print("2️⃣ Initializing Knowledge Retriever...")
    retriever = get_knowledge_retriever()
    
    if not retriever.is_enabled():
        print("   ❌ Knowledge Retriever is disabled")
        print("   Check that Elasticsearch is running and Python dependencies are installed")
        return False
    
    print("   ✅ Knowledge Retriever initialized\n")
    
    # 3. Test indexing
    print("3️⃣ Testing conversation indexing...")
    success = retriever.index_conversation(
        message="What is Python?",
        response="Python is a high-level programming language known for its simplicity and readability.",
        user_id="test_user",
        conversation_id="test_conv",
        app_type="test"
    )
    
    if success:
        print("   ✅ Successfully indexed test conversation\n")
    else:
        print("   ❌ Failed to index conversation\n")
        return False
    
    # 4. Test search
    print("4️⃣ Testing semantic search...")
    results = retriever.search(
        query="Tell me about Python programming",
        top_k=1,
        user_id="test_user"
    )
    
    if results:
        print(f"   ✅ Found {len(results)} result(s)")
        print(f"   - Query: 'Tell me about Python programming'")
        print(f"   - Match: '{results[0]['message']}'")
        print(f"   - Score: {results[0].get('score', 'N/A')}\n")
    else:
        print("   ⚠️  No results found (may need to wait for indexing)\n")
    
    # 5. Get stats
    print("5️⃣ Getting statistics...")
    stats = retriever.get_stats()
    print(f"   ✅ Knowledge Base Stats:")
    print(f"   - Enabled: {stats['enabled']}")
    print(f"   - Total Conversations: {stats.get('total_conversations', 0)}")
    print(f"   - Embedding Dimension: {stats.get('embedding_dim', 0)}")
    print(f"   - Index: {stats.get('index_name', 'N/A')}\n")
    
    # 6. Cleanup
    print("6️⃣ Cleaning up test data...")
    retriever.delete_conversation("test_conv")
    print("   ✅ Test data cleaned\n")
    
    print("=" * 60)
    print("🎉 Knowledge Layer is fully operational!")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    test_installation()
```

Run the test:
```bash
python test_knowledge_layer.py
```

**Expected Output:**
```
🧪 Testing Knowledge Layer Installation

1️⃣ Checking configuration...
   ✅ Config loaded
   - Elasticsearch: localhost:9200
   - Meilisearch: localhost:7700
   - Redis: localhost:6379

2️⃣ Initializing Knowledge Retriever...
   ✅ Knowledge Retriever initialized

3️⃣ Testing conversation indexing...
   ✅ Successfully indexed test conversation

4️⃣ Testing semantic search...
   ✅ Found 1 result(s)
   - Query: 'Tell me about Python programming'
   - Match: 'What is Python?'
   - Score: 0.85

5️⃣ Getting statistics...
   ✅ Knowledge Base Stats:
   - Enabled: True
   - Total Conversations: 1
   - Embedding Dimension: 384
   - Index: companion_knowledge

6️⃣ Cleaning up test data...
   ✅ Test data cleaned

============================================================
🎉 Knowledge Layer is fully operational!
============================================================
```

---

## 🧪 Testing

### Test 1: Basic Functionality

```python
from companion_baas.knowledge import get_knowledge_retriever

retriever = get_knowledge_retriever()

# Index some conversations
retriever.index_conversation(
    message="How do I install Python?",
    response="You can install Python from python.org...",
    user_id="user1"
)

retriever.index_conversation(
    message="What are Python decorators?",
    response="Decorators are a way to modify function behavior...",
    user_id="user1"
)

# Search for similar questions
results = retriever.search("How to set up Python?", top_k=2)

for r in results:
    print(f"Q: {r['message']}")
    print(f"A: {r['response']}")
    print(f"Score: {r['score']}")
    print()
```

### Test 2: RAG Context Retrieval

```python
from companion_baas.knowledge import get_knowledge_retriever

retriever = get_knowledge_retriever()

# Get formatted context for a query
context = retriever.get_context_for_query(
    query="What is machine learning?",
    max_context_length=1000
)

print(context)
# Use this context in your LLM prompts!
```

### Test 3: Performance Test

```python
import time
from companion_baas.knowledge import get_knowledge_retriever

retriever = get_knowledge_retriever()

# Index 100 conversations
print("Indexing 100 conversations...")
start = time.time()

for i in range(100):
    retriever.index_conversation(
        message=f"Test question {i}",
        response=f"Test response {i}",
        user_id="perf_test"
    )

end = time.time()
print(f"Indexed 100 conversations in {end-start:.2f}s")

# Search test
print("\nSearching...")
start = time.time()
results = retriever.search("Test question", top_k=10)
end = time.time()

print(f"Search completed in {end-start:.3f}s")
print(f"Found {len(results)} results")

# Cleanup
retriever.delete_conversation("perf_test")
```

---

## 🐛 Troubleshooting

### Issue 1: "Elasticsearch connection error"

**Symptoms:**
```
❌ Elasticsearch connection error: ...
```

**Solutions:**

1. **Check if Elasticsearch is running:**
   ```bash
   docker ps | grep elasticsearch
   curl http://localhost:9200
   ```

2. **Check Docker logs:**
   ```bash
   docker logs companion_elasticsearch
   ```

3. **Restart Elasticsearch:**
   ```bash
   docker-compose restart elasticsearch
   ```

4. **Check port availability:**
   ```bash
   lsof -i :9200  # Should show elasticsearch
   ```

### Issue 2: "sentence-transformers not installed"

**Symptoms:**
```
⚠️ sentence-transformers not installed
```

**Solution:**
```bash
pip install sentence-transformers
# This will also install torch and transformers
```

### Issue 3: "Failed to load embedding model"

**Symptoms:**
```
❌ Failed to load embedding model: ...
```

**Solutions:**

1. **Check internet connection** (model downloads from HuggingFace)

2. **Manually download model:**
   ```python
   from sentence_transformers import SentenceTransformer
   model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
   ```

3. **Check disk space:**
   ```bash
   df -h  # Model is ~90MB
   ```

### Issue 4: "Knowledge Retriever disabled"

**Symptoms:**
```
⚠️ Knowledge Retriever disabled (dependencies not available)
```

**Solution:**

Check each component:

```python
from companion_baas.knowledge import get_elasticsearch_client, get_vector_store

# Test Elasticsearch
es = get_elasticsearch_client()
print(f"ES enabled: {es.enabled}")

# Test Vector Store
vs = get_vector_store()
print(f"Vector store enabled: {vs.enabled}")
```

Fix whichever component is disabled.

### Issue 5: "Out of memory" (Docker)

**Symptoms:**
```
Elasticsearch container keeps restarting
```

**Solution:**

Reduce memory limits in `docker-compose.yml`:

```yaml
elasticsearch:
  environment:
    - "ES_JAVA_OPTS=-Xms256m -Xmx256m"  # Reduced from 512m
```

Then restart:
```bash
docker-compose down
docker-compose up -d
```

### Issue 6: Slow search performance

**Solutions:**

1. **Check index size:**
   ```python
   retriever = get_knowledge_retriever()
   stats = retriever.get_stats()
   print(stats)
   ```

2. **Reduce top_k:**
   ```python
   # Instead of top_k=10
   results = retriever.search(query, top_k=5)
   ```

3. **Use vector search only (faster):**
   ```python
   results = retriever.search(query, search_type='vector')
   ```

---

## 🎯 Next Steps

Now that your Knowledge Layer is set up:

1. **Integrate with existing brain:**
   - See `INTEGRATION_GUIDE.md`

2. **Set up Meilisearch:**
   - See Phase 2 in `BRAIN_INTEGRATION_MASTER_PLAN.md`

3. **Add web intelligence:**
   - See Phase 3 for Crawl4AI integration

4. **Build your first RAG application:**
   - See examples in `examples/` directory

---

## 📚 Resources

- [Elasticsearch Documentation](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
- [Sentence Transformers](https://www.sbert.net/)
- [Meilisearch Docs](https://www.meilisearch.com/docs)
- [Redis Documentation](https://redis.io/docs/)

---

## 💬 Support

Having issues? Check:

1. **Logs:**
   ```bash
   docker-compose logs -f
   ```

2. **Service health:**
   ```bash
   docker-compose ps
   curl http://localhost:9200/_cluster/health
   ```

3. **Python errors:**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

---

**🎉 Congratulations! You've successfully set up the Companion Brain Knowledge Layer!**

The brain can now:
- ✅ Remember past conversations
- ✅ Search semantically across all knowledge
- ✅ Provide context-aware responses using RAG
- ✅ Learn from every interaction

Next: Integrate with your existing BaaS code!
