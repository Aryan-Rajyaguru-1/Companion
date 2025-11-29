# 🚀 Companion BaaS - Quick Reference

## Installation
```bash
cd "Companion deepthink"
# BaaS is ready to use in companion_baas/ directory
```

## Basic Usage

### 1. Simple Chat (Quickest Way)
```python
from companion_baas.sdk import quick_chat

response = quick_chat("What is Python?")
print(response)
```

### 2. Chatbot Application
```python
from companion_baas.sdk import BrainClient

client = BrainClient(app_type="chatbot")
response = client.chat("Hello!", user_id="user123")
print(response['response'])
```

### 3. Code Assistant
```python
from companion_baas.sdk import BrainClient

client = BrainClient(app_type="coder")
response = client.chat(
    "Create a Python function to calculate factorial",
    tools=['code']
)
print(response['response'])
```

### 4. Research Tool
```python
from companion_baas.sdk import BrainClient

client = BrainClient(app_type="research")
response = client.chat(
    "Latest AI developments in 2025",
    tools=['web', 'deepsearch']
)
print(response['response'])
```

## SDK Methods

### BrainClient

```python
client = BrainClient(app_type="chatbot")

# Send message
response = client.chat(message, user_id, conversation_id, tools)

# Quick ask
answer = client.ask(question)

# Get history
history = client.get_history(user_id, conversation_id, limit=10)

# Clear history
client.clear_history(user_id, conversation_id)

# Web search
results = client.search(query, deep=True)

# Get stats
stats = client.get_stats()

# Provide feedback
client.feedback(message_id, rating=5, comment="Great!")
```

## App Types

| Type | Use Case | Default Tools |
|------|----------|---------------|
| `chatbot` | Conversation | None |
| `coder` | Programming | `['code']` |
| `research` | Research | `['web', 'deepsearch']` |
| `assistant` | General help | `['web']` |
| `tutor` | Education | `['web']` |
| `analyst` | Data analysis | `['think', 'deepsearch']` |

## Tools

| Tool | Description |
|------|-------------|
| `web` | Web search |
| `code` | Code optimization |
| `think` | Deep reasoning |
| `deepsearch` | Comprehensive research |
| `research` | Research with analysis |

## Response Format

```python
{
    'response': str,        # The AI's response text
    'metadata': {
        'model': str,       # Model used
        'source': str,      # Provider (Groq, OpenRouter, etc.)
        'response_time': float,
        'thinking_data': str,  # For reasoning models
        'links': list,      # Reference links if any
        'tools_used': list
    },
    'success': bool,        # Request success status
    'error': str           # Error if any
}
```

## Examples

### Flask Integration
```python
from flask import Flask, request, jsonify
from companion_baas.sdk import BrainClient

app = Flask(__name__)
brain = BrainClient(app_type="chatbot")

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    response = brain.chat(
        message=data['message'],
        user_id=data.get('user_id')
    )
    return jsonify(response)
```

### FastAPI Integration
```python
from fastapi import FastAPI
from companion_baas.sdk import BrainClient

app = FastAPI()
brain = BrainClient(app_type="chatbot")

@app.post("/chat")
async def chat(message: str, user_id: str):
    response = brain.chat(message, user_id=user_id)
    return response
```

### CLI Application
```python
from companion_baas.sdk import BrainClient

client = BrainClient(app_type="chatbot")

while True:
    user_input = input("You: ")
    if user_input.lower() == 'quit':
        break
    
    response = client.ask(user_input)
    print(f"Bot: {response}")
```

## Common Patterns

### Conversation with Context
```python
client = BrainClient(app_type="chatbot")
user_id = "user123"
conv_id = "conv456"

# Message 1
response1 = client.chat("Hi", user_id=user_id, conversation_id=conv_id)

# Message 2 (brain remembers context)
response2 = client.chat("What did I just say?", user_id=user_id, conversation_id=conv_id)
```

### With Custom Tools
```python
response = client.chat(
    "Search for Python tutorials",
    tools=['web']  # Enable web search
)
```

### With Custom Context
```python
response = client.chat(
    "Fix this code",
    code=buggy_code,
    language="python",
    error_message="TypeError on line 5"
)
```

## Configuration

```python
client = BrainClient(
    app_type="chatbot",
    enable_caching=True,   # Cache responses
    enable_search=True,     # Allow web search
    enable_learning=True    # Learn from feedback
)
```

## Statistics

```python
stats = client.get_stats()

print(f"Total Requests: {stats['total_requests']}")
print(f"Success Rate: {stats['success_rate']}%")
print(f"Cached Responses: {stats['cached_responses']}")
print(f"Avg Response Time: {stats['average_response_time']:.2f}s")
print(f"Models Used: {stats['models_used']}")
```

## Error Handling

```python
response = client.chat("Hello")

if response['success']:
    print(response['response'])
else:
    print(f"Error: {response.get('error')}")
```

## Testing

```bash
# Run chatbot example
python companion_baas/examples/chatbot_example.py

# Run coder example
python companion_baas/examples/coder_example.py

# Run research example
python companion_baas/examples/research_example.py
```

## Troubleshooting

### Import Error
```python
# Make sure you're in the project root
import sys
import os
sys.path.insert(0, '/path/to/Companion deepthink')
```

### Dependencies
```bash
# Install parent project dependencies
cd "Companion deepthink"
pip install -r requirements.txt
```

## Resources

- **README.md** - Complete documentation
- **ARCHITECTURE.md** - Technical details
- **MIGRATION_GUIDE.md** - Migration steps
- **examples/** - Working examples

## Support

- 📧 Email: support@companion-ai.dev
- 💬 Issues: GitHub Issues
- 📖 Docs: See README.md

---

**Quick Start Template:**

```python
from companion_baas.sdk import BrainClient

# 1. Initialize
client = BrainClient(app_type="chatbot")

# 2. Chat
response = client.chat("Your message here")

# 3. Use response
print(response['response'])
```

**That's it! Start building! 🚀**
