#!/bin/bash
# Neural Layer Setup Script for Dell Latitude 7480
# Lightweight AI processing layer

echo "🚀 Setting up Neural Layer for Companion AI..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Activate virtual environment
echo "📦 Activating virtual environment..."
cd "/home/aryan/Documents/Companion deepthink"
source .venv/bin/activate

# Install dependencies
echo "⬇️  Installing lightweight dependencies..."
echo "   - spacy (12MB model)"
echo "   - scikit-learn (fast TF-IDF)"
echo "   - beautifulsoup4 (web scraping)"
pip install spacy==3.7.0 scikit-learn==1.3.0 beautifulsoup4==4.12.2

# Download spaCy model
echo "📥 Downloading spaCy small model (12MB)..."
python -m spacy download en_core_web_sm

echo ""
echo "✅ Neural Layer Setup Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Resource Usage:"
echo "   - Total Size: ~80MB"
echo "   - RAM Usage: ~200MB"
echo "   - CPU Usage: ~30%"
echo ""
echo "🎯 Next Steps:"
echo "   1. Restart backend: cd website && python chat-backend.py"
echo "   2. Test with: 'What is the current height of BTS members?'"
echo "   3. Check stats at: /api/neural/stats"
echo ""
