#!/bin/bash

# GitHub Setup Script for Companion Project
# This script helps you push your project to GitHub

echo "🚀 GitHub Setup for Companion Project"
echo "======================================="
echo ""

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "❌ Git is not installed. Please install Git first."
    exit 1
fi

echo "📋 Your GitHub Credentials:"
echo "   Username: Aryan-Rajyaguru-1"
echo "   Repository: companion"
echo ""

# Check if already a git repository
if [ ! -d ".git" ]; then
    echo "🔧 Initializing Git repository..."
    git init
    echo "✅ Git repository initialized"
else
    echo "✅ Git repository already exists"
fi

# Add all files
echo "📁 Adding all files to Git..."
git add .

# Create initial commit
echo "💾 Creating initial commit..."
git commit -m "Initial commit: Companion v3.0 - AI Chat Interface

Features:
- Modern GUI for local Ollama and cloud OpenRouter models
- Interactive web demo with real-time chat
- Smart download system with OS detection
- Complete documentation and support pages
- Backend API for AI model inference
- Testing suite for model evaluation

Contact: Rajyaguru Aryan
Email: aryanrajyaguru2007@gmail.com
Phone: +91 76002 30560"

# Set up remote origin
echo "🔗 Setting up GitHub remote..."
git remote remove origin 2>/dev/null || true
git remote add origin https://github.com/Aryan-Rajyaguru-1/companion.git

echo ""
echo "🚀 Next Steps:"
echo "1. Create a new repository named 'companion' on GitHub:"
echo "   → Go to https://github.com/new"
echo "   → Repository name: companion"
echo "   → Description: AI Chat Interface for Local & Cloud Models"
echo "   → Make it Public"
echo "   → Don't initialize with README (we already have one)"
echo ""
echo "2. Push to GitHub:"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "3. Your repository will be available at:"
echo "   https://github.com/Aryan-Rajyaguru-1/companion"
echo ""
echo "📧 If you need help, contact: aryanrajyaguru2007@gmail.com"
echo "📱 Phone: +91 76002 30560"
