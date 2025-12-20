#!/bin/bash
# Setup script for Neural Layer

echo "🧠 Setting up Neural Layer for Companion AI..."
echo "================================================"

# Activate virtual environment if it exists
if [ -d "../.venv" ]; then
    echo "✅ Activating virtual environment..."
    source ../.venv/bin/activate
elif [ -d ".venv" ]; then
    echo "✅ Activating virtual environment..."
    source .venv/bin/activate
fi

# Install lightweight dependencies
echo "📦 Installing lightweight neural dependencies..."
pip install spacy==3.7.0 scikit-learn==1.3.0 -q

# Download small spaCy model (12MB)
echo "⬇️  Downloading spaCy small English model (12MB)..."
python -m spacy download en_core_web_sm

echo ""
echo "✅ Neural Layer setup complete!"
echo ""
echo "📊 Installed components:"
echo "  • spaCy v3.7.0 (~12MB)"
echo "  • scikit-learn v1.3.0 (~8MB)"
echo "  • en_core_web_sm model"
echo ""
echo "💡 Total additional space: ~20MB"
echo "💻 Expected RAM usage: ~200-300MB"
echo "⚡ CPU usage: ~25-35%"
echo ""
echo "🚀 Ready to use! Restart chat-backend.py to activate."
