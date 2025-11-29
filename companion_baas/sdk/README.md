# Companion BaaS SDK

Easy-to-use Python SDK for integrating advanced AI capabilities into any application.

## 🚀 Quick Start

```python
from companion_baas.sdk import BrainClient

# Initialize
client = BrainClient(app_type="chatbot")

# Basic chat
response = client.ask("What is Python?")
print(response)
```

## ✨ Features

### **6 Core Phases**
1. **Knowledge Layer** - Semantic search & vector database
2. **Search Engine** - Fast hybrid search (<50ms)
3. **Web Intelligence** - Web scraping & news APIs
4. **Execution & Generation** - Code execution & 23+ tools
5. **Optimization** - Caching & performance monitoring
6. **Advanced Features** - 8 advanced capabilities (see below)

### **8 Advanced Capabilities** (100% FREE)

#### 1. Advanced Reasoning
```python
# Chain-of-Thought reasoning
result = client.reason(
    "If I have 3 apples and buy 2 more, how many do I have?",
    strategy="chain_of_thought"
)
print(result['answer'])
print(f"Reasoning steps: {len(result['steps'])}")

# Available strategies:
# - "chain_of_thought": Step-by-step linear reasoning
# - "tree_of_thought": Branching exploration
# - "self_reflection": Iterative refinement
# - "react": Reasoning + Acting loop
# - "auto": Auto-select best strategy
```

#### 2. Memory Persistence
```python
# Store memories
client.remember(
    user_id="user123",
    content="User prefers Python over JavaScript",
    memory_type="preference",
    importance=0.9
)

# Recall memories
memories = client.recall(
    user_id="user123",
    query="programming language",
    limit=5
)

for memory in memories:
    print(f"{memory['content']} (importance: {memory['importance']})")
```

#### 3. Real-time Learning
```python
# Provide feedback
client.provide_learning_feedback(
    user_id="user123",
    interaction_id="msg_456",
    feedback_type="rating",  # or "correction", "preference", "flag"
    value=5
)

# System learns from patterns and adapts responses
```

#### 4. Streaming Responses
```python
import asyncio

async def stream_example():
    async for chunk in client.stream_think(
        "Explain quantum computing",
        show_reasoning=True
    ):
        if chunk['event'] == 'token':
            print(chunk['content'], end='', flush=True)
        elif chunk['event'] == 'thinking':
            print(f"\n[Thinking: {chunk['content']}]")

asyncio.run(stream_example())
```

#### 5. Multi-Modal Processing
```python
from core.multimodal import MediaInput, ModalityType

# Process image
result = client.process_media(
    media_inputs=[
        MediaInput(
            type=ModalityType.IMAGE,
            content="path/to/image.jpg"
        )
    ],
    prompt="What's in this image?"
)

# Process audio
result = client.process_media(
    media_inputs=[
        MediaInput(
            type=ModalityType.AUDIO,
            content="path/to/audio.mp3"
        )
    ],
    prompt="Transcribe this audio"
)

# Supports: images, audio, video, PDF documents
```

#### 6. Multi-Agent Coordination
```python
import asyncio

async def multi_agent_example():
    result = await client.delegate_task(
        task="Research Python web frameworks and create a comparison table",
        use_multiple_agents=True,
        decompose=True
    )
    
    print(f"Result: {result['result']}")
    print(f"Agents used: {result['agents_used']}")
    print(f"Subtasks: {len(result['subtasks'])}")

asyncio.run(multi_agent_example())
```

#### 7. Code Execution
```python
# Execute Python code
result = client.execute_code(
    code="for i in range(5): print(i**2)",
    language="python"
)
print(result['output'])

# Execute JavaScript
result = client.execute_code(
    code="console.log([1,2,3].map(x => x * 2))",
    language="javascript"
)
```

#### 8. Built-in Tools
```python
# List available tools
tools = client.list_tools()
print(f"Available: {tools}")

# Use tools
result = client.call_tool("add", 10, 20)
print(result)  # 30

result = client.call_tool("count_words", "Hello World")
print(result)  # 2
```

## 🎯 App Types

Choose the right mode for your application:

```python
# Conversational AI
client = BrainClient(app_type="chatbot")

# Code assistant
client = BrainClient(app_type="coder")

# Research assistant
client = BrainClient(app_type="research")

# Educational tutor
client = BrainClient(app_type="tutor")

# Data analyst
client = BrainClient(app_type="analyst")

# General assistant (default)
client = BrainClient(app_type="assistant")
```

## 🆓 Bytez Integration (100% FREE)

- **141,000+ AI models** (0-10B parameters)
- **Unlimited tokens, images, videos**
- **1 concurrent request** (sequential execution)
- **No credit card required**
- **Vision, audio, multimodal support**

The SDK automatically uses Bytez for all LLM operations when available.

## 📊 Capabilities Check

```python
# Check what's available
caps = client.get_advanced_capabilities()

if caps['enabled']:
    print("Advanced features available!")
    for name, enabled in caps['capabilities'].items():
        print(f"  {'✅' if enabled else '❌'} {name}")

# Get statistics
stats = client.get_stats()
print(f"Total requests: {stats['total_requests']}")
print(f"Phases enabled: {len(stats['phases_enabled'])}")
```

## 🔧 Advanced Configuration

```python
# Custom configuration
config = {
    'bytez_available': True,
    'max_context_length': 4096,
    'temperature': 0.7
}

client = BrainClient(
    app_type="chatbot",
    config=config
)
```

## 📝 Complete Example

```python
from companion_baas.sdk import BrainClient
import asyncio

async def main():
    # Initialize
    client = BrainClient(app_type="chatbot")
    
    # Basic chat
    response = client.ask("Hello! What can you do?")
    print(f"Bot: {response}\n")
    
    # Advanced reasoning
    result = client.reason(
        "What's 15% of 80?",
        strategy="chain_of_thought"
    )
    print(f"Answer: {result['answer']}\n")
    
    # Store memory
    client.remember(
        "user123",
        "User is learning Python",
        importance=0.8
    )
    
    # Recall memory
    memories = client.recall("user123", "Python")
    print(f"Memories: {len(memories)}\n")
    
    # Execute code
    result = client.execute_code("print(sum([1,2,3,4,5]))")
    print(f"Code output: {result['output']}\n")
    
    # Streaming
    print("Streaming: ", end='')
    async for chunk in client.stream_think("Count to 5"):
        if chunk['event'] == 'token':
            print(chunk['content'], end='', flush=True)
    print("\n")
    
    # Check capabilities
    caps = client.get_advanced_capabilities()
    print(f"✅ All {len(caps['capabilities'])} advanced capabilities enabled!")

if __name__ == "__main__":
    asyncio.run(main())
```

## 🐛 Troubleshooting

### Bytez Rate Limit
If you see "1 concurrent request" errors, ensure requests are sequential:
```python
# ❌ Don't do concurrent requests
results = [client.ask(q) for q in questions]

# ✅ Do sequential requests
results = []
for q in questions:
    results.append(client.ask(q))
```

### Import Delays
First import may take 5-10 seconds as it checks optional services. Subsequent imports are instant.

### Optional Dependencies
Install for full multi-modal support:
```bash
pip install soundfile opencv-python PyPDF2 python-docx
```

## 📚 Documentation

- [Brain Architecture](../core/README.md)
- [Advanced Features](../core/ADVANCED_FEATURES.md)
- [API Reference](../docs/API.md)

## 🤝 Support

- Issues: [GitHub Issues](https://github.com/Aryan-Rajyaguru-1/Companion/issues)
- Docs: [Full Documentation](../README.md)

---

**Made with ❤️ by the Companion Team**

*Empowering developers to build intelligent applications with ease*
