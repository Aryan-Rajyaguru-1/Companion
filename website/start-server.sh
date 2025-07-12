#!/bin/bash

# Companion Testing Suite - Web Server Launcher
# This script starts a local web server to serve the testing interface

echo "🚀 Starting Companion Testing Suite Web Server..."
echo "📂 Serving files from: $(pwd)"
echo "🌐 Access URLs:"
echo "   • Classic UI: http://localhost:8000/index.html"
echo "   • Modern UI: http://localhost:8000/grok-index.html"
echo "   • Features: http://localhost:8000/features.html"
echo "   • Models: http://localhost:8000/models.html"
echo "   • Testing Suite: http://localhost:8000/testing.html"
echo "   • Demo Page: http://localhost:8000/demo.html"
echo "   • Download Page: http://localhost:8000/download.html"
echo "   • Contact Us: http://localhost:8000/contact.html"
echo "   • Documentation: http://localhost:8000/documentation.html"
echo "   • Help Center: http://localhost:8000/help.html"
echo ""
echo "💡 Tip: Press Ctrl+F5 to force refresh and clear cache"
echo ""

# Check if Python is available
if command -v python3 &> /dev/null; then
    echo "🐍 Using Python 3..."
    python3 -m http.server 8000
elif command -v python &> /dev/null; then
    echo "🐍 Using Python 2..."
    python -m SimpleHTTPServer 8000
else
    echo "❌ Error: Python not found!"
    echo "Please install Python to run the web server."
    exit 1
fi
