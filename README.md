# DeepCompanion v2.0 🤖

A modern, beautiful GUI chat interface for interacting with multiple Ollama AI models locally. Now supports both conversation and code generation modes with dual-model architecture!

![Python](https://img.shields.io/badge/python-v3.7+-blue.svg)
![Platform](https://img.shields.io/badge/platform-linux%20%7C%20windows%20%7C%20macos-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## ✨ New in v2.0

### 🔄 **Dual-Model Support**
- **💬 Conversation Mode**: DeepSeek R1 1.5B for general discussions and reasoning
- **💻 Code Mode (Fast)**: CodeGemma 2B for quick code generation (optimized for performance)
- **🧠 Code Mode (Advanced)**: CodeQwen 7B for complex programming tasks
- **Seamless switching** between models with separate chat histories
- **Model-specific optimizations** for better performance

### 🛠️ **Code Generation Features**
- **Syntax highlighting** for code blocks in chat
- **Copy code blocks** with one click
- **Format input text** with basic code formatting
- **Optimized parameters** for code generation (lower temperature, higher token limits)
- **Code-specific UI elements** that appear only in code mode

### ⌨️ **Enhanced UX**
- **Keyboard shortcuts** for quick model switching (Ctrl+1, Ctrl+2, Ctrl+3)
- **Menu bar** with organized commands
- **Model status indicators** showing availability of each model
- **Context-aware help system**
- **Improved error handling** and user feedback
- **Performance optimizations** for older hardware (Intel i7-7600U, 8GB RAM)

## Features ✨

- **Modern Chat Interface**: Clean, intuitive design with dark theme
- **Dual-Model Architecture**: Switch between conversation and code generation modes
- **Performance Optimized**: Fast CodeGemma 2B for quick responses, advanced CodeQwen 7B for complex tasks
- **Real-time Streaming**: Live response generation with typing indicators
- **Connection Monitoring**: Automatic detection of Ollama service and model status
- **Separate Chat Histories**: Each model maintains its own conversation context
- **Code Tools**: Copy, format, and highlight code blocks
- **Keyboard Shortcuts**: 
  - `Enter` to send messages
  - `Ctrl+Enter` for new lines
  - `Ctrl+1/2/3` for model switching
  - `Ctrl+L` to clear chat
  - `Ctrl+C` to copy selection or last code block
  - `F1` for help
- **Hardware Optimized**: Configured for Intel i7-7600U with 8GB RAM
- **Responsive Design**: Adapts to different window sizes

## Prerequisites 📋

Before running DeepCompanion v2.0, ensure you have:

1. **Python 3.7+** installed on your system
2. **Ollama** installed and running
3. **AI models** pulled and available:
   - DeepSeek R1 1.5B (conversation)
   - CodeGemma 2B (fast code generation) - **Recommended for Intel i7-7600U**
   - CodeQwen 7B (advanced code generation) - Optional for complex tasks

### Ollama Setup

If you haven't already set up Ollama with the models:

```bash
# Install Ollama (if not already installed)
curl -fsSL https://ollama.com/install.sh | sh

# Pull required models
ollama pull deepseek-r1:1.5b    # 1.1 GB - Conversation & reasoning
ollama pull codegemma:2b        # 1.6 GB - Fast code generation (recommended)

# Optional: Pull advanced code model for complex tasks
ollama pull codeqwen:7b         # 4.2 GB - Advanced code generation

# Verify models are available
ollama list
```

**Hardware Requirements:**
- **CPU**: Intel i7-7600U or equivalent (2+ cores recommended)
- **RAM**: 8GB+ (4GB available for models recommended)
- **Storage**: ~3GB free space for recommended models (~7GB for all models)
- **OS**: Linux, Windows, or macOS

## Installation 🚀

1. **Clone or download** this project to your local machine

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Ensure Ollama is running**:
   ```bash
   # Check if Ollama service is running
   curl http://localhost:11434/api/tags
   
   # If not running, start it
   ollama serve
   ```

## Usage 💬

### Basic Usage

1. **Start the application**:
   ```bash
   python main.py
   ```

2. **Wait for connection**: The app will automatically connect to Ollama and verify available models

3. **Choose your mode**:
   - **💬 Conversation Mode**: For general discussions, questions, analysis
   - **💻 Code Mode (Fast)**: For quick programming tasks, debugging, simple scripts
   - **🧠 Code Mode (Advanced)**: For complex algorithms, large codebases, detailed explanations

4. **Start chatting**: Type your message and press Enter to send

### Model Switching

- **Click model buttons** at the top to switch between modes
- **Keyboard shortcuts**: `Ctrl+1` (Conversation), `Ctrl+2` (Code Fast), `Ctrl+3` (Code Advanced)
- Each model maintains **separate chat history**
- Status indicators show model availability: ✅ Ready, ❌ Missing, ⏳ Checking

### Performance Tips

- **Start with CodeGemma 2B** (Fast mode) for most coding tasks - optimized for your hardware
- **Switch to CodeQwen 7B** (Advanced mode) only when you need more sophisticated responses
- **Response times on Intel i7-7600U**:
  - CodeGemma 2B: ~2-5 seconds
  - CodeQwen 7B: ~10-30 seconds
  - DeepSeek R1: ~3-8 seconds

### Code Mode Features

When in Code Mode, you'll see additional tools:
- **Copy Code Button**: Extracts and copies the last code block to clipboard
- **Format Input Button**: Basic code formatting for your input
- **Enhanced highlighting**: Code blocks are visually highlighted
- **Optimized settings**: 
  - Fast mode: Lower temperature, faster generation for quick solutions
  - Advanced mode: Balanced settings for detailed, complex code

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message |
| `Ctrl+Enter` | New line in input |
| `Ctrl+1` | Switch to Conversation mode |
| `Ctrl+2` | Switch to Code mode (Fast) |
| `Ctrl+3` | Switch to Code mode (Advanced) |
| `Ctrl+L` | Clear current chat |
| `Ctrl+C` | Copy selection or last code block |
| `F1` | Show help dialog |

## Configuration ⚙️

The application uses these default settings:

- **Ollama URL**: `http://localhost:11434`
- **Models**: 
  - Conversation: `deepseek-r1:1.5b`
  - Code (Fast): `codegemma:2b`
  - Code (Advanced): `codeqwen:7b`
- **Timeout**: 120 seconds for API requests

### Model Parameters

**Conversation Mode:**
- Temperature: 0.7 (creative responses)
- Top-p: 0.9
- Max tokens: 2048

**Code Mode (Fast - CodeGemma 2B):**
- Temperature: 0.2 (focused, quick responses)
- Top-p: 0.7
- Max tokens: 2048
- Top-k: 20 (optimized for speed)

**Code Mode (Advanced - CodeQwen 7B):**
- Temperature: 0.3 (precise code generation)
- Top-p: 0.8
- Max tokens: 4096
- Repeat penalty: 1.1

To customize models, modify the `models` dictionary in `main.py`:

```python
self.model_name = "your-preferred-model"
```

## Interface Guide 🎯

### Main Window
- **Title Bar**: Shows "DeepCompanion - AI Chat Interface"
- **Status Bar**: Connection status and current model info
- **Chat Area**: Scrollable conversation history
- **Input Area**: Text box for typing messages
- **Action Buttons**: Send and Clear Chat buttons

### Status Indicators
- ✅ **Green**: Connected and ready
- ❌ **Red**: Connection or model issues
- ⚠️ **Orange**: Warnings (e.g., model not found)
- 🤔 **Blue**: AI is processing your request

## Troubleshooting 🔧

### Common Issues

1. **"Ollama not accessible"**
   - Ensure Ollama service is running: `ollama serve`
   - Check if port 11434 is available
   - Verify firewall settings

2. **"Model not found"**
   - Pull the model: `ollama pull deepseek-r1:1.5b`
   - Check available models: `ollama list`
   - Verify model name spelling

3. **"Request timed out"**
   - Large responses may take time on CPU-only systems
   - Consider using a smaller model for faster responses
   - Check system resources

4. **GUI not responding**
   - Force close and restart the application
   - Check Python and tkinter installation

### System Requirements

- **Minimum RAM**: 4GB (8GB+ recommended for better performance)
- **CPU**: Any modern processor (GPU not required for DeepSeek R1 1.5B)
- **Storage**: ~2GB for the model
- **Network**: Local connection to Ollama service

## Development 🛠️

### Project Structure
```
DeepCompanion/
├── main.py                 # Main application file
├── requirements.txt        # Python dependencies
├── README.md              # This file
└── .github/
    └── copilot-instructions.md  # Development guidelines
```

### Key Classes and Methods

- `DeepCompanion`: Main application class
  - `setup_styles()`: Configure UI themes and colors
  - `create_widgets()`: Build the interface
  - `send_message()`: Handle user input
  - `get_ollama_response()`: Communicate with Ollama API

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Future Enhancements 🚀

Potential improvements for future versions:

- [ ] Multiple model support with switching
- [ ] Conversation export/import
- [ ] Custom themes and styling options
- [ ] Voice input/output capabilities
- [ ] Plugin system for extensions
- [ ] Multi-language support
- [ ] Advanced prompt templates
- [ ] Conversation search functionality

## License 📄

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments 🙏

- **Ollama Team**: For the excellent local AI model serving platform
- **DeepSeek**: For the powerful R1 model
- **Python Community**: For the amazing tkinter and requests libraries

## Support 💪

If you encounter issues or have questions:

1. Check the troubleshooting section above
2. Verify your Ollama setup is working correctly
3. Ensure all dependencies are installed
4. Check that the DeepSeek R1 model is available

---

**Happy chatting with your AI companion!** 🎉
