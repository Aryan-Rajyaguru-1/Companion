#!/bin/bash

# Companion AI Chat Assistant - Web Server Launcher
# This script starts a local web server to serve the Companion website
# 
# Contact: aryanrajyaguru2007@gmail.com
# Phone: +91 76002 30560
# GitHub: https://github.com/Aryan-Rajyaguru-1/Companion

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
echo "   • Main Website: http://localhost:$PORT/index.html"
echo "   • Modern Chat UI: http://localhost:$PORT/grok-index.html"
echo "   • Features: http://localhost:$PORT/features.html"
echo "   • AI Models: http://localhost:$PORT/models.html"
echo "   • 🔧 Get API Integration: http://localhost:$PORT/index.html#get-api"
echo "   • Download: http://localhost:$PORT/download.html"
echo "   • Contact Us: http://localhost:$PORT/contact.html"
echo "   • Documentation: http://localhost:$PORT/documentation.html"
echo "   • Help Center: http://localhost:$PORT/help.html"
echo "   • Demo/Testing: http://localhost:$PORT/demo.html"
echo ""
echo "🔑 API Integration Features:"
echo "   • Generate API keys instantly"
echo "   • RESTful endpoints for conversation management"
echo "   • Multiple AI model access (GPT-4, Claude, Gemini, DeepSeek)"
echo "   • Built-in web search and intelligent caching"
echo "   • Code examples in cURL, Python, JavaScript, PHP"
echo "   • Time-sensitive data handling"
echo "   • Unified Companion AI platform access"
echo ""
echo "🤖 AI Mode Options:"
echo ""
echo "   🌐 WEB MODE (Cloud AI Only):"
echo "      ✨ Use Companion directly in your browser"
echo "      ☁️  Powered by cloud-based AI models only"
echo "      🚀 No download or installation required"
echo "      🔄 Always up-to-date with latest features"
echo "      🌍 Requires internet connection"
echo "      💡 Perfect for: Quick AI chats, testing, web browsing"
echo ""
echo "   💻 DESKTOP MODE (Cloud + Local AI):"
echo "      📥 Download the Companion desktop application"
echo "      ☁️  Access to cloud AI models (when online)"
echo "      🖥️  Use local AI models (works offline)"
echo "      🔒 Best performance and privacy"
echo "      ⚡ Hybrid capabilities: Cloud speed + Offline privacy"
echo "      💡 Perfect for: Power users, offline work, privacy-focused usage"
echo ""
echo "   🎯 Choose Your Mode:"
echo "      • Want to try quickly? → Use Web Mode (cloud AI only)"
echo "      • Want full features? → Download Desktop Mode (cloud + local AI)"
echo "      • Need offline AI? → Must download Desktop Mode"
echo "      • Privacy focused? → Download Desktop Mode for local AI"
echo ""
echo "   📋 Feature Comparison:"
echo "      ┌─────────────────────┬─────────────┬─────────────────┐"
echo "      │ Feature             │ Web Mode    │ Desktop Mode    │"
echo "      ├─────────────────────┼─────────────┼─────────────────┤"
echo "      │ Cloud AI Models     │ ✅ Yes      │ ✅ Yes          │"
echo "      │ Local AI Models     │ ❌ No       │ ✅ Yes          │"
echo "      │ Offline Usage       │ ❌ No       │ ✅ Yes          │"
echo "      │ Installation        │ ❌ None     │ 📥 Required     │"
echo "      │ Privacy Level       │ 🔵 Standard │ 🔒 Enhanced     │"
echo "      │ Performance         │ 🌐 Good     │ ⚡ Excellent    │"
echo "      └─────────────────────┴─────────────┴─────────────────┘"
echo ""
echo "📁 Source Code & Development:"
echo "   • GitHub Repository: https://github.com/Aryan-Rajyaguru-1/Companion"
echo "   • Local Files: $(pwd)"
echo "   • Directory Listing: http://localhost:$PORT/"
echo ""
echo "💡 Tips:"
echo "   • Press Ctrl+F5 to force refresh and clear cache"
echo "   • Visit http://localhost:$PORT/ to browse all files"
echo "   • Source code available on GitHub and locally"
echo ""

# Check if Python is available and start server
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
