#!/bin/bash

# Companion AI Chat Assistant - Web Server Launcher
# This script starts a local web server to serve the Companion website
# 
# 📧 Contact: aryanrajyaguru2007@gmail.com
# 📱 Phone: +91 76002 30560
# 🌐 GitHub: https://github.com/Aryan-Rajyaguru-1/Companion

# Find an available port
PORT=8000
while netstat -tuln 2>/dev/null | grep -q ":$PORT "; do
    PORT=$((PORT + 1))
done

echo "🚀 Starting Companion AI Chat Assistant Web Server..."
echo "📂 Serving files from: $(pwd)"
echo "📧 Contact: aryanrajyaguru2007@gmail.com | 📱 +91 76002 30560"
echo ""
echo "🌐 Access URLs:"
echo "   • Classic UI: http://localhost:$PORT/index.html"
echo "   • Modern UI: http://localhost:$PORT/grok-index.html"
echo "   • Features: http://localhost:$PORT/features.html"
echo "   • Models: http://localhost:$PORT/models.html"
echo "   • Download: http://localhost:$PORT/download.html"
echo "   • Contact Us: http://localhost:$PORT/contact.html"
echo "   • Documentation: http://localhost:$PORT/documentation.html"
echo "   • Help Center: http://localhost:$PORT/help.html"
echo "   • Demo/Testing: http://localhost:$PORT/demo.html"
echo ""
echo "🤖 AI Mode Options:"
echo "   • 🌐 Web Mode (Cloud AI): Use directly in browser - no download required"
echo "   • 💻 Desktop Mode (Local AI): Download app for offline AI + cloud options"
echo "   • ⚡ Hybrid Mode: Best of both - cloud speed + offline privacy"
echo ""
echo "� Usage Modes:"
echo "   🌐 WEB MODE (Cloud AI Only):"
echo "      • Use Companion directly in your browser"
echo "      • No download or installation required"
echo "      • Powered by cloud-based AI models"
echo "      • Always up-to-date with latest features"
echo "      • Requires internet connection"
echo ""
echo "   💻 DESKTOP MODE (Online + Offline AI):"
echo "      • Download the Companion desktop app"
echo "      • Use local AI models (works offline)"
echo "      • Access to cloud AI models (when online)"
echo "      • Best performance and privacy"
echo "      • Hybrid cloud + local AI capabilities"
echo ""
echo "   💡 Recommendation:"
echo "      • Try Web Mode first - no download needed!"
echo "      • Download Desktop Mode for offline AI + better performance"
echo ""
echo "�📁 Source Code & Development:"
echo "   • GitHub Repository: https://github.com/Aryan-Rajyaguru-1/Companion"
echo "   • Local Files: $(pwd)"
echo "   • Directory Listing: http://localhost:$PORT/"
echo ""
echo "💡 Tips:"
echo "   • Press Ctrl+F5 to force refresh and clear cache"
echo "   • Visit http://localhost:$PORT/ to browse all files"
echo "   • Source code available on GitHub and locally"
echo ""

# Check if Python is available and find an available port
echo "🌐 Starting server on port $PORT..."
echo ""

if command -v python3 &> /dev/null; then
    echo "🐍 Using Python 3..."
    python3 -m http.server $PORT
elif command -v python &> /dev/null; then
    echo "🐍 Using Python 2..."
    python -m SimpleHTTPServer $PORT
else
    echo "❌ Error: Python not found!"
    echo "Please install Python to run the web server."
    exit 1
fi
