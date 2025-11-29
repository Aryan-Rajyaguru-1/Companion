# Companion BaaS - Thread-Based Architecture Documentation

## Overview

CompanionBrain now features a **comprehensive thread-based architecture** where ALL modules run in dedicated threads, managed autonomously by the brain itself. The brain makes intelligent decisions about thread lifecycle, resource allocation, and performance optimization.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     COMPANION BRAIN                          │
│                  (Autonomous Control)                        │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           THREAD MANAGER                              │  │
│  │     (Centralized Thread Management)                   │  │
│  │                                                        │  │
│  │  • Auto-scaling                                        │  │
│  │  • Health monitoring                                   │  │
│  │  • Self-healing                                        │  │
│  │  • Resource optimization                               │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       │                                      │
│         ┌─────────────┼─────────────┐                       │
│         │             │             │                        │
│         ▼             ▼             ▼                        │
│    ┌────────┐   ┌────────┐   ┌────────┐                   │
│    │ CORE   │   │ PHASES │   │  AGI   │                   │
│    │THREADS │   │THREADS │   │THREADS │                   │
│    └────────┘   └────────┘   └────────┘                   │
│         │             │             │                        │
│         └─────────────┴─────────────┘                       │
│                       │                                      │
│                       ▼                                      │
│              ALL MODULE THREADS                              │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
           ┌───────────────────────┐
           │     SDK WRAPPER        │
           │   (BrainClient)        │
           └───────────────────────┘
                        │
                        ▼
           ┌───────────────────────┐
           │  CLIENT APPLICATIONS   │
           │ (Chatbot, Coder, etc.) │
           └───────────────────────┘
```

## Thread Categories

### 1. Core Threads (Priority: CRITICAL/HIGH)
- **model_router**: Routes requests to appropriate AI models
- **context_manager**: Manages conversation context and history

### 2. Phase Threads
#### Phase 1: Knowledge Layer (Priority: HIGH)
- **knowledge_retriever**: Retrieves information from knowledge base

#### Phase 2: Search Engine (Priority: MEDIUM)
- **search_engine**: Performs search operations

#### Phase 3: Web Intelligence (Priority: MEDIUM)
- **web_crawler**: Crawls and extracts web content

#### Phase 4: Code Execution (Priority: HIGH)
- **code_executor**: Executes code safely in sandbox

#### Phase 5: Optimization (Priority: LOW)
- **optimizer**: Optimizes brain performance based on metrics

### 3. Advanced Threads (Priority: HIGH/MEDIUM)
- **advanced_reasoning**: Performs deep reasoning tasks
- **multimodal_processor**: Processes multimodal inputs (text, image, audio)

### 4. AGI Threads (Tier 4)
- **personality_engine** (Priority: MEDIUM): Manages personality and emotional state
- **neural_reasoning** (Priority: HIGH): Advanced neural reasoning
- **self_learning** (Priority: MEDIUM): Learns from interactions
- **autonomous_system** (Priority: HIGH): Makes autonomous decisions

### 5. Monitoring Threads
- **system_monitor**: Health checks every 5 seconds
- **autonomous_thread_manager**: Makes autonomous decisions every 10 seconds

## Autonomous Decision-Making

The brain autonomously manages threads by making intelligent decisions:

### Decision Types

1. **Scale Up**
   - Triggered when: All threads in category are busy
   - Action: Increase max_threads for category by 2
   - Example: If all 5 search_engine threads are busy, create 2 more

2. **Scale Down**
   - Triggered when: Thread utilization < 30%
   - Action: Suggest scale-down (idle threads)
   - Example: If only 1 of 7 threads active, scale down

3. **Self-Healing**
   - Triggered when: Thread state = ERROR
   - Action: Auto-restart failed thread
   - Example: If web_crawler crashes, automatically restart it

### Decision Process

```python
# Every 10 seconds, the brain:
1. Get system status
2. Analyze thread health
3. Make decisions based on:
   - Thread utilization
   - Error rates
   - Queue sizes
   - Priority levels
4. Execute decisions autonomously
```

## Usage Examples

### Basic Usage with Threads

```python
from companion_baas.sdk import BrainClient

# Create brain (threads auto-start)
brain = BrainClient(
    app_type="chatbot",
    enable_agi=True,
    enable_search=True
)

# Get thread status
status = brain.get_thread_status()
print(f"Active threads: {status['active_threads']}/{status['total_threads']}")
print(f"Categories: {status['categories']}")

# Check specific module
personality_status = brain.get_module_thread_status('personality_engine')
print(f"Personality engine: {personality_status['state']}")
print(f"Tasks completed: {personality_status['tasks_completed']}")
print(f"Success rate: {personality_status['success_rate']:.2%}")
```

### Viewing Autonomous Decisions

```python
# Get decision history
decisions = brain.get_thread_decisions()
print(f"Total decisions made: {len(decisions)}")

for decision in decisions[-10:]:  # Last 10 decisions
    print(f"[{decision['timestamp']}] {decision['type']}")
    print(f"  Context: {decision['context']}")
    print(f"  Data: {decision['data']}")
```

### Manual Thread Control

```python
# Pause a module temporarily
brain.pause_module('web_crawler')
print("Web crawler paused")

# Resume when needed
brain.resume_module('web_crawler')
print("Web crawler resumed")
```

### Submit Custom Tasks

```python
# Submit task to specific module thread
task_id = brain.submit_task_to_module(
    module_name='personality_engine',
    function=lambda msg: analyze_personality(msg),
    args=("Hello, how are you?",),
    priority='high'
)
print(f"Task submitted: {task_id}")
```

### Graceful Shutdown

```python
# When application closes
brain.shutdown(timeout=15.0)
print("All threads shut down gracefully")
```

## Thread Statistics

### Per-Thread Metrics

Each thread tracks:
- `tasks_completed`: Number of tasks successfully completed
- `tasks_failed`: Number of failed tasks
- `success_rate`: Percentage of successful tasks
- `uptime`: Time since thread started (seconds)
- `queue_size`: Number of pending tasks
- `state`: Current state (running, paused, error, stopped)
- `last_activity`: Timestamp of last activity

### System-Wide Metrics

```python
status = brain.get_thread_status()

# Overall statistics
print(f"Total threads created: {status['stats']['total_threads_created']}")
print(f"Tasks completed: {status['stats']['total_tasks_completed']}")
print(f"Tasks failed: {status['stats']['total_tasks_failed']}")
print(f"Auto-scale events: {status['stats']['threads_auto_scaled']}")
print(f"Threads restarted: {status['stats']['threads_restarted']}")
print(f"System uptime: {status['uptime']:.2f}s")
```

### Category-Level Metrics

```python
# Check each category
for category, stats in status['categories'].items():
    print(f"\n{category}:")
    print(f"  Active: {stats['active']}")
    print(f"  Total: {stats['total']}")
    print(f"  Max: {stats['max']}")
    print(f"  Utilization: {stats['active']/stats['max']*100:.1f}%")
```

## Benefits

### 1. **Autonomous Management**
- Brain decides when to scale up/down
- Self-healing from failures
- Intelligent resource allocation

### 2. **Performance**
- Parallel processing of all modules
- Non-blocking operations
- Optimized thread count per category

### 3. **Reliability**
- Auto-restart failed threads
- Health monitoring every 5 seconds
- Graceful degradation if thread fails

### 4. **Observability**
- Real-time thread status
- Decision history
- Comprehensive metrics

### 5. **Control**
- Pause/resume modules
- Custom task submission
- Priority-based scheduling

## Thread Priorities

Threads are assigned priorities for intelligent scheduling:

```python
CRITICAL = 1  # User-facing, must respond immediately (model_router)
HIGH = 2      # Important background (knowledge, code execution, AGI)
MEDIUM = 3    # Standard operations (search, personality, learning)
LOW = 4       # Optimization, analytics
IDLE = 5      # Cleanup, maintenance (run when nothing else active)
```

## Configuration

### Default Limits

```python
# Maximum threads per category (auto-scales if needed)
'core': 10 threads
'phase1': 5 threads (Knowledge)
'phase2': 5 threads (Search)
'phase3': 8 threads (Web Intelligence)
'phase4': 6 threads (Code Execution)
'phase5': 4 threads (Optimization)
'advanced': 8 threads (Advanced features)
'agi': 6 threads (AGI components)
'monitoring': 3 threads (Health checks)

# Total: max 50 threads (configurable)
```

### Auto-Scaling

When enabled (default), the brain will:
- Increase max_threads by 2 when category is fully utilized
- Track all scaling events in statistics
- Make decisions every 10 seconds

## Integration with Chatbot Backend

```python
# website/chat-backend-baas.py
from companion_baas.sdk import BrainClient

# Initialize with AGI and threads
companion_brain = BrainClient(
    app_type="chatbot",
    enable_caching=True,
    enable_search=True,
    enable_learning=True,
    enable_agi=True,  # Enables AGI threads
    enable_autonomy=False
)

# Add endpoint to get thread status
@app.route('/api/threads/status', methods=['GET'])
def get_thread_status():
    try:
        status = companion_brain.get_thread_status()
        return jsonify({
            'success': True,
            'data': status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Add endpoint for thread decisions
@app.route('/api/threads/decisions', methods=['GET'])
def get_thread_decisions():
    try:
        decisions = companion_brain.get_thread_decisions()
        return jsonify({
            'success': True,
            'data': decisions[-50:]  # Last 50 decisions
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
```

## Best Practices

### 1. Monitor Thread Health

```python
# Regular health check
status = brain.get_thread_status()
for module, thread_status in status['module_threads'].items():
    if thread_status['success_rate'] < 0.8:  # < 80%
        print(f"⚠️ {module} has low success rate!")
```

### 2. Let the Brain Decide

```python
# Don't manually create threads - brain does it automatically
# ❌ Don't do this:
# brain.create_thread("my_custom_thread")

# ✅ Do this instead:
# Let brain manage threads, just submit tasks
brain.submit_task_to_module('model_router', my_function, args=(data,))
```

### 3. Clean Shutdown

```python
# Always shutdown gracefully when application exits
import atexit

brain = BrainClient(app_type="chatbot")
atexit.register(lambda: brain.shutdown(timeout=10.0))
```

### 4. Use Priorities Wisely

```python
# User requests = CRITICAL
brain.submit_task_to_module('model_router', process_user_query, priority='critical')

# Background learning = MEDIUM
brain.submit_task_to_module('self_learning', update_knowledge, priority='medium')

# Optimization = LOW
brain.submit_task_to_module('optimizer', analyze_performance, priority='low')
```

## Troubleshooting

### Thread Not Starting

```python
# Check if thread manager is enabled
status = brain.get_thread_status()
if not status['enabled']:
    print("Thread manager not available - running synchronously")
```

### High Error Rate

```python
# Check thread errors
thread_status = brain.get_module_thread_status('web_crawler')
if thread_status['tasks_failed'] > 10:
    print(f"Errors: {thread_status['errors']}")
```

### Thread Stuck

```python
# Check last activity
import datetime
thread_status = brain.get_module_thread_status('search_engine')
last_activity = datetime.datetime.fromisoformat(thread_status['last_activity'])
idle_time = (datetime.datetime.now() - last_activity).total_seconds()

if idle_time > 300:  # 5 minutes
    print(f"Thread idle for {idle_time}s - may be stuck")
    # Brain's autonomous manager will detect and restart automatically
```

## Future Enhancements

- [ ] Thread affinity (pin threads to CPU cores)
- [ ] Dynamic priority adjustment based on workload
- [ ] Thread pool per category for better isolation
- [ ] Advanced metrics (CPU%, memory per thread)
- [ ] Thread communication channels (inter-module messaging)
- [ ] Thread dependencies (start A before B)
- [ ] Distributed threading (across multiple machines)

## Summary

The thread-based architecture provides:

✅ **Autonomous thread management** - Brain makes all decisions
✅ **Zero client changes** - Same imports, just works
✅ **Auto-scaling** - Adapts to workload automatically  
✅ **Self-healing** - Restarts failed threads
✅ **Full observability** - Status, metrics, decisions
✅ **Manual control** - Pause/resume when needed
✅ **Priority scheduling** - Critical tasks first
✅ **Graceful shutdown** - Clean resource cleanup

**All modules → Threads → Thread Manager → Brain → SDK → Client**

The brain is now a true autonomous system that manages its own resources!
