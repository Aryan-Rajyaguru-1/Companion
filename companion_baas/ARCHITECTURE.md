# 🏗️ Companion BaaS Architecture

## Overview

Companion BaaS separates the **Brain** (AI intelligence) from the **Body** (applications).

```
╔═══════════════════════════════════════════════════════════╗
║               COMPANION BaaS FRAMEWORK                    ║
║                    (The Brain)                            ║
╠═══════════════════════════════════════════════════════════╣
║                                                           ║
║  ┌─────────────────────────────────────────────────┐    ║
║  │         CompanionBrain (Core Engine)            │    ║
║  │  • Request Processing                           │    ║
║  │  • Context Management                           │    ║
║  │  • Statistics Tracking                          │    ║
║  └──────────────┬──────────────────────────────────┘    ║
║                 │                                         ║
║  ┌──────────────┼──────────────────────────────────┐    ║
║  │              │                                   │    ║
║  ▼              ▼                                   ▼    ║
║  ┌──────────┐  ┌──────────┐  ┌──────────────────┐      ║
║  │  Model   │  │ Context  │  │    Response      │      ║
║  │  Router  │  │ Manager  │  │   Processor      │      ║
║  └──────────┘  └──────────┘  └──────────────────┘      ║
║       │                                                   ║
║       ▼                                                   ║
║  ┌─────────────────────────────────────────────────┐    ║
║  │         API Wrapper (Unified Interface)         │    ║
║  │  • OpenRouter Integration                       │    ║
║  │  • Groq API                                     │    ║
║  │  • HuggingFace                                  │    ║
║  │  • Ollama Local                                 │    ║
║  │  • Search Engine Wrapper                       │    ║
║  └─────────────────────────────────────────────────┘    ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
                          │
                          │ SDK Interface
                          │
         ┌────────────────┼────────────────┐
         │                │                │
         ▼                ▼                ▼
    ┌─────────┐      ┌─────────┐      ┌─────────┐
    │Chatbot  │      │  Coder  │      │Research │
    │  App    │      │   App   │      │   App   │
    └─────────┘      └─────────┘      └─────────┘
```

## Core Components

### 1. CompanionBrain (core/brain.py)

**Purpose:** Main orchestrator that handles all AI requests

**Responsibilities:**
- Process incoming requests
- Manage conversation contexts
- Route to appropriate handlers
- Handle caching
- Track statistics
- Manage errors and fallbacks

**Key Methods:**
```python
think(message, context, tools, user_id, conversation_id)
  → Returns: {'response': str, 'metadata': dict, 'success': bool}

get_conversation_history(user_id, conversation_id, limit)
  → Returns: List of messages

clear_conversation(user_id, conversation_id)
  → Clears history

get_stats()
  → Returns: Brain statistics
```

### 2. API Wrapper (Reused from Companion)

**Purpose:** Unified interface to multiple AI providers

**Integrations:**
- **OpenRouter** - Access to GPT-4, Claude, etc.
- **Groq** - Ultra-fast inference (800 tok/s)
- **HuggingFace** - Free tier with 1000+ models
- **Ollama** - Local models (fallback)
- **Search Engines** - DuckDuckGo, SearX, etc.

**Smart Features:**
- Automatic fallback if primary model fails
- Model selection based on task type
- Rate limiting and error handling
- Response caching

### 3. BrainClient (SDK)

**Purpose:** Simple interface for apps to use the brain

**Why?**
- Apps don't need to know about AI internals
- Just send message, get response
- Handles all complexity internally

**Usage:**
```python
client = BrainClient(app_type="chatbot")
response = client.ask("Hello!")
```

## Data Flow

### Request Flow
```
1. App sends request
   ↓
2. BrainClient receives
   ↓
3. CompanionBrain processes
   ↓
4. Check cache (if enabled)
   ↓
5. Get/create conversation context
   ↓
6. Determine tools needed
   ↓
7. Call API Wrapper
   ↓
8. API Wrapper selects best model
   ↓
9. Make API call(s) with fallbacks
   ↓
10. Process response
    ↓
11. Cache response
    ↓
12. Update context
    ↓
13. Return to app
```

### Context Management
```
User/Conversation
       ↓
   Brain stores in memory:
   {
     'user_123': {
       'history': [
         {'role': 'user', 'content': 'Hello'},
         {'role': 'assistant', 'content': 'Hi!'}
       ],
       'metadata': {
         'created_at': datetime,
         'app_type': 'chatbot'
       }
     }
   }
```

### Caching Strategy
```
Cache Key = hash(message + tools + app_type + has_history)
           ↓
   Check cache
           ↓
   Hit? → Return cached (< 0.1s)
           ↓
   Miss? → Generate new response
           ↓
        Cache for TTL:
        - With history: 30 min
        - Without history: 60 min
```

## Separation of Concerns

### The Brain (BaaS) Handles:
✅ **AI Logic**
- Model selection
- Prompt engineering
- Response generation
- Context management
- Caching strategies

✅ **Integration**
- API calls
- Search integration
- Error handling
- Fallback logic

✅ **Optimization**
- Response caching
- Rate limiting
- Performance tracking

### The App Handles:
✅ **UI/UX**
- User interface
- User interactions
- Display formatting

✅ **Business Logic**
- App-specific features
- User authentication
- Data persistence

✅ **Deployment**
- Hosting
- Monitoring
- Scaling

## Plug & Play Architecture

### How Any App Can Use the Brain:

```python
# Step 1: Import
from companion_baas.sdk import BrainClient

# Step 2: Initialize
brain = BrainClient(app_type="your_app_type")

# Step 3: Use
response = brain.chat("User message")

# That's it! No AI knowledge needed!
```

### App Types Supported:

| App Type | Auto-Optimizations | Default Tools |
|----------|-------------------|---------------|
| chatbot | General conversation models | None |
| coder | Code-optimized models | ['code'] |
| research | Research models + search | ['web', 'deepsearch'] |
| image_gen | Image generation models | None |
| video_gen | Video generation models | None |
| assistant | Multi-purpose models | ['web'] |
| tutor | Educational focus | ['web'] |
| analyst | Analysis + thinking | ['think', 'deepsearch'] |

## Scalability

### Current: Monolithic
```
Flask App (chat-backend.py)
├── HTTP endpoints
├── AI logic (mixed)
└── Database
```

### With BaaS: Separated
```
Flask App                  Brain Service
├── HTTP endpoints  →→→→  ├── AI logic
└── Database              ├── Model routing
                          └── Caching
```

### Future: Microservices
```
┌─────────────┐
│   Frontend  │
└──────┬──────┘
       │
   ┌───▼────────────┐
   │ API Gateway    │
   └───┬────────────┘
       │
  ┌────┼─────────┬─────────┐
  │    │         │         │
  ▼    ▼         ▼         ▼
┌───┐ ┌───────┐ ┌───┐   ┌───┐
│API│ │Brain  │ │DB │   │...│
│   │ │Service│ │   │   │   │
└───┘ └───────┘ └───┘   └───┘
      (BaaS)
```

## Security Model

### Current Issues:
❌ API keys mixed in code
❌ Logic exposed in client-facing app
❌ Hard to audit AI behavior

### With BaaS:
✅ **Centralized secrets** - API keys in brain only
✅ **Logic isolation** - Apps can't access internal AI logic
✅ **Audit trail** - All AI requests go through brain
✅ **Rate limiting** - Brain enforces limits centrally
✅ **Access control** - Can add auth to brain API

## Performance Optimizations

### 1. Intelligent Caching
- Cache based on: message + context + tools
- TTL varies by query type
- Reduces API calls by ~40%

### 2. Model Selection
- Fast models for simple queries
- Powerful models for complex tasks
- Automatic fallback if model fails

### 3. Parallel Processing
- Multiple model queries in parallel
- Search + AI generation concurrently
- Fastest response wins

### 4. Connection Pooling
- Reuse HTTP connections
- Reduce latency
- Better throughput

## Future Enhancements

### Phase 2: REST API Server
```python
# Run brain as standalone service
from companion_baas.server import BrainServer

server = BrainServer(host='0.0.0.0', port=8080)
server.run()

# Apps connect via HTTP
POST http://brain-server:8080/v1/chat
{
  "message": "Hello",
  "app_id": "chatbot_v1",
  "user_id": "user123"
}
```

### Phase 3: Advanced Features
- **Streaming responses** - Real-time token streaming
- **Multi-modal** - Text + images + audio
- **Fine-tuning** - Custom model training
- **Analytics dashboard** - Visual insights
- **Plugin system** - Extensible tools
- **Load balancing** - Multiple brain instances

### Phase 4: Enterprise
- **Multi-tenancy** - Separate brains per customer
- **Usage billing** - Track API costs per app
- **SLA monitoring** - Uptime guarantees
- **Backup/Recovery** - Data persistence
- **Compliance** - GDPR, SOC2, etc.

## Comparison

### Before BaaS:
```python
# 200+ lines of mixed code
@app.route('/api/chat')
def chat():
    # Model selection logic
    # API key management
    # Prompt engineering
    # Error handling
    # Caching logic
    # Search integration
    # Response formatting
    return jsonify(response)
```

### After BaaS:
```python
# 10 lines!
@app.route('/api/chat')
def chat():
    brain = BrainClient(app_type="chatbot")
    response = brain.chat(request.json['message'])
    return jsonify(response)
```

## Summary

**Companion BaaS** = Universal AI Brain that any app can use

**Key Benefits:**
1. 🧠 **Build AI logic once**, use everywhere
2. 🔌 **Plug & Play** - 3 lines to add AI
3. 🎯 **Focused apps** - UI separate from AI
4. 🚀 **Easy updates** - Update brain, all apps benefit
5. 🔒 **Secure** - Centralized with proper isolation
6. 📊 **Observable** - Built-in analytics
7. 💰 **Cost-effective** - Reuse instead of rebuild

**One Brain, Infinite Possibilities** 🌟
