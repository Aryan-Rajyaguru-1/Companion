# 🚀 DeepCompanion v3.0 - Quick Start Guide

## ✅ OpenRouter Integration Complete!

Your DeepCompanion application now supports both **local Ollama models** and **cloud OpenRouter models** with your provided API keys.

## 🎯 Quick Test

```bash
# 1. Test the integration
python test_openrouter.py

# 2. Launch the application  
python main.py
```

## 🤖 Available Models

### 🏠 Local Models (Ollama)
- 💬 **Chat Mode**: Llama 3.2 3B - Natural conversation
- 🤔 **Think Mode**: DeepSeek R1 1.5B - Reasoning & analysis  
- 💻 **Code Mode**: CodeGemma 2B - Everyday coding
- 🧠 **Advanced Mode**: CodeQwen 7B - Complex programming

### ☁️ Cloud Models (OpenRouter)
- 🧠 **DeepSeek R1** - Advanced reasoning and step-by-step analysis
- ⚡ **Gemini 2.5 Flash** - Google's fast multimodal AI
- 🤖 **GPT-4o** - OpenAI's most advanced multimodal model
- 💻 **Mistral Devstral** - Specialized for code generation
- 🚀 **GPT-4.1** - Enhanced GPT-4 with improved capabilities
- 🔍 **Perplexity Sonar** - Deep research with real-time web search

## 🎮 How to Use

1. **Start the app**: `python main.py`
2. **Local models**: Use the first tab for Ollama models (fast, private)
3. **Cloud models**: Use the second tab for OpenRouter models (advanced)
4. **Chat naturally**: The app handles routing automatically
5. **Switch anytime**: Click tabs or use keyboard shortcuts (Ctrl+1-4 for local)

## ⌨️ Keyboard Shortcuts

- `Enter` - Send message
- `Ctrl+Enter` - New line in input
- `Ctrl+L` - Clear current chat
- `Ctrl+1-4` - Switch local models  
- `F1` - Show help
- `Ctrl+C` - Copy selection or last code block

## 🔧 Technical Details

- **Local**: Requires Ollama running on `localhost:11434`
- **Cloud**: Uses your 6 OpenRouter API keys automatically
- **Context**: Separate chat history for each model
- **Streaming**: Real-time responses from both providers
- **Fallback**: Graceful handling if services unavailable

## 🌐 Website

Check out the modern landing page in the `website/` directory:
- `website/index.html` - Responsive landing page
- `website/styles.css` - Modern dark theme styling

## 🎉 You're All Set!

Your DeepCompanion now offers the best of both worlds:
- 🏠 **Local**: Fast, private, offline-capable
- ☁️ **Cloud**: Advanced, latest models, unlimited scale

**Happy chatting!** 🚀✨

---

*Need help? Press F1 in the app or check the About dialog for more information.*
