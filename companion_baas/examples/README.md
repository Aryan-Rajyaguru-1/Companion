# 📚 Companion BaaS Examples

This directory contains example chatbots demonstrating the upgrade path from traditional to AGI.

## 🎯 Quick Start

### 1. Basic Chatbot (Traditional - No Changes)

```bash
python examples/chatbot_basic.py
```

**What it shows:**
- ✅ Traditional `BrainClient` usage
- ✅ 100% compatible with existing code
- ✅ Simple ask/response pattern

**Perfect for:**
- Existing chatbot apps
- Simple Q&A bots
- Lightweight applications

---

### 2. AGI Chatbot (One Line Upgrade)

```bash
python examples/chatbot_agi.py
```

**What it shows:**
- ✅ Instant upgrade to AGI Brain
- ✅ Unique personality per brain
- ✅ Learning from conversations
- ✅ Personality commands (`/personality`, `/stats`)

**Perfect for:**
- Testing AGI features
- Personality-driven chatbots
- Self-learning applications

---

### 3. Advanced AGI Chatbot (Full Features)

```bash
python examples/chatbot_advanced.py
```

**What it shows:**
- ✅ All AGI capabilities
- ✅ Concept teaching
- ✅ Memory recall
- ✅ Creative synthesis
- ✅ Optional autonomous mode

**Commands:**
- `/personality` - View personality profile with trait scores
- `/stats` - Learning system statistics
- `/agi` - AGI system status
- `/teach <concept>` - Teach new concepts with examples
- `/recall <query>` - Recall related memories
- `/synthesize` - Creative idea synthesis
- `/autonomy` - Toggle self-modification (⚠️ advanced)

**Perfect for:**
- Production AGI chatbots
- Research assistants
- Advanced conversational AI

---

### 4. Side-by-Side Comparison

```bash
python examples/comparison_demo.py
```

**What it shows:**
- ✅ Traditional and AGI running together
- ✅ Response comparison
- ✅ Coexistence demonstration
- ✅ Feature differences

**Perfect for:**
- Understanding the upgrade
- Seeing both approaches
- Migration planning

---

## 📊 Feature Matrix

| Feature | Basic | AGI | Advanced |
|---------|-------|-----|----------|
| Simple Chat | ✅ | ✅ | ✅ |
| Unique Personality | ❌ | ✅ | ✅ |
| Learning | ❌ | ✅ | ✅ |
| Memory Recall | ❌ | ❌ | ✅ |
| Concept Teaching | ❌ | ❌ | ✅ |
| Creative Synthesis | ❌ | ❌ | ✅ |
| Autonomous Mode | ❌ | ❌ | ✅ |

---

## 🔧 Requirements

All examples use the same dependencies from `requirements.txt`:

```bash
# Install dependencies
pip install -r requirements.txt

# Optional: Install Ollama for local models
# Visit: https://ollama.ai
```

---

## 💡 Usage Tips

### **For Existing Chatbots:**

1. **Try Basic Example** - Verify your setup works
2. **Try AGI Example** - See the one-line upgrade
3. **Compare** - Run comparison demo to see differences
4. **Migrate** - Switch your chatbot when ready

### **For New Chatbots:**

- **Start with AGI** (`chatbot_agi.py`) for built-in intelligence
- **Use Advanced** if you need full AGI capabilities
- **Traditional** only if you need minimal overhead

---

## 🚀 Integration Guide

### **Upgrade Your Existing Chatbot:**

```python
# Before (your existing code)
from companion_baas.sdk import BrainClient
client = BrainClient(app_type="chatbot")

# After (one line change!)
from companion_baas import Brain
brain = Brain(app_type="chatbot")

# Everything else stays the same!
response = brain.ask("Hello!")  # Same API
```

### **Access AGI Features:**

```python
# Get personality
personality = brain.get_personality()
print(f"Personality: {personality['personality_id']}")
print(f"Emotion: {personality['emotion']}")

# Check learning progress
stats = brain.get_learning_stats()
print(f"Learned: {stats['episodes']} conversations")

# Teach concepts
brain.teach_concept("customer_service", [
    "Be polite and helpful",
    "Listen to concerns",
    "Provide clear solutions"
])

# Recall memories
memories = brain.recall_memories("customer support", limit=5)

# Creative synthesis
result = brain.synthesize_ideas(
    ["AI", "Support", "Efficiency"],
    "Improve customer experience"
)
```

---

## 🔐 Safety Notes

### **Autonomous Mode (⚠️ Advanced)**

The `chatbot_advanced.py` example includes autonomous mode, which allows the brain to:
- Make decisions automatically
- Modify its own code
- Execute improvement cycles

**Default:** Disabled for safety

**To enable:**
```python
brain.enable_autonomy(auto_approve_low_risk=True)
```

**⚠️ Only enable if:**
- You understand self-modification implications
- You have proper monitoring
- You're ready for autonomous behavior

---

## 📖 Documentation

- **[Migration Guide](../MIGRATION_GUIDE.md)** - Complete upgrade guide
- **[Tier 4 Roadmap](../TIER4_AGI_ROADMAP.md)** - AGI architecture details
- **[API Reference](../README.md)** - Full API documentation

---

## 🎯 Next Steps

1. ✅ Run the examples
2. ✅ Pick the approach that fits your needs
3. ✅ Integrate into your application
4. ✅ Enable AGI features gradually
5. ✅ Monitor and optimize

---

## ✨ Summary

- **100% Backwards Compatible** - Existing code works unchanged
- **One-Line Upgrade** - Just change the import to get AGI
- **Gradual Migration** - Use both traditional and AGI together
- **Production Ready** - All examples tested and working

**Your chatbot is ready for AGI!** 🚀
