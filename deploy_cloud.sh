#!/bin/bash
# Quick Cloud Deployment Script for Companion Brain

set -e

echo "🚀 Companion Brain - Cloud Deployment Helper"
echo "============================================="
echo ""

# Check if git repo
if [ ! -d .git ]; then
    echo "❌ Not a git repository. Initializing..."
    git init
    git add .
    git commit -m "Initial commit - Companion Brain with AGI"
fi

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo "📝 You have uncommitted changes. Committing them..."
    git add .
    git commit -m "Prepare for cloud deployment"
fi

echo ""
echo "Choose your cloud platform:"
echo "1. Railway (Recommended - Easiest)"
echo "2. Render (Best free tier)"
echo "3. Fly.io (More control)"
echo ""
read -p "Enter choice (1-3): " choice

case $choice in
    1)
        echo ""
        echo "📦 Railway Deployment"
        echo "===================="
        echo ""
        echo "Steps:"
        echo "1. Push to GitHub:"
        echo "   git remote add origin YOUR_GITHUB_URL"
        echo "   git push -u origin main"
        echo ""
        echo "2. Go to: https://railway.app"
        echo "3. Click 'Start a New Project'"
        echo "4. Select 'Deploy from GitHub repo'"
        echo "5. Choose this repository"
        echo "6. Set environment variables:"
        echo "   - API_KEY: (generate a strong key)"
        echo "   - ENVIRONMENT: production"
        echo "   - LOG_LEVEL: INFO"
        echo ""
        echo "7. Railway will auto-deploy! 🎉"
        echo ""
        echo "Generate API key:"
        python3 -c "import secrets; print(f'API_KEY={secrets.token_urlsafe(32)}')"
        ;;
    
    2)
        echo ""
        echo "🎨 Render Deployment"
        echo "==================="
        echo ""
        echo "Steps:"
        echo "1. Push to GitHub (if not done):"
        echo "   git remote add origin YOUR_GITHUB_URL"
        echo "   git push -u origin main"
        echo ""
        echo "2. Go to: https://render.com"
        echo "3. Click 'New +' → 'Web Service'"
        echo "4. Connect your GitHub repository"
        echo "5. Settings:"
        echo "   - Build: pip install -r requirements-api.txt"
        echo "   - Start: uvicorn api_server:app --host 0.0.0.0 --port \$PORT"
        echo "   - Plan: Free"
        echo ""
        echo "6. Environment variables:"
        python3 -c "import secrets; print(f'   API_KEY={secrets.token_urlsafe(32)}')"
        echo "   ENVIRONMENT=production"
        echo "   LOG_LEVEL=INFO"
        echo ""
        echo "7. Click 'Create Web Service'"
        ;;
    
    3)
        echo ""
        echo "✈️  Fly.io Deployment"
        echo "===================="
        echo ""
        
        # Check if flyctl is installed
        if ! command -v fly &> /dev/null; then
            echo "Installing Fly CLI..."
            curl -L https://fly.io/install.sh | sh
            echo ""
            echo "⚠️  Fly CLI installed. Please restart your terminal and run this script again."
            exit 0
        fi
        
        echo "Logging in to Fly.io..."
        fly auth login
        
        echo ""
        echo "Launching app..."
        fly launch --no-deploy
        
        echo ""
        echo "Setting secrets..."
        API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
        fly secrets set API_KEY=$API_KEY
        
        echo ""
        echo "Deploying..."
        fly deploy
        
        echo ""
        echo "✅ Deployed to Fly.io!"
        echo "Your API: $(fly info --host)"
        echo "API Key: $API_KEY"
        echo ""
        echo "Monitor: fly logs"
        echo "Status: fly status"
        ;;
    
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "📚 Next steps:"
echo "1. Test your API: curl https://YOUR_URL/health"
echo "2. Read CLOUD_DEPLOYMENT.md for usage examples"
echo "3. Use the Python client in client_library.py"
echo ""
echo "✨ Your Companion Brain is ready for the cloud!"
