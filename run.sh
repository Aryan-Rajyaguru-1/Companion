#!/bin/bash
# DeepCompanion Launcher Script

echo "🤖 Starting DeepCompanion..."
echo "Checking Ollama connection..."

# Check if Ollama is running
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✅ Ollama is running"
    echo "🚀 Launching DeepCompanion..."
    "/home/aryan/Documents/Companion deepthink/.venv/bin/python" main.py
else
    echo "❌ Ollama is not running or not accessible"
    echo "Please start Ollama first:"
    echo "  ollama serve"
    echo ""
    echo "Then run this script again or execute:"
    echo "  python main.py"
    exit 1
fi
