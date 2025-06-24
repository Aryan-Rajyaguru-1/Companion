#!/bin/bash

# GitHub Repository Setup Commands
# This script will prompt for your GitHub username

echo "🚀 DeepCompanion GitHub Setup"
echo "=============================="

# Check if repository already exists on GitHub
if [ -z "$1" ]; then
    echo ""
    echo "Please provide your GitHub username as an argument:"
    echo "Usage: ./github-setup.sh YOUR_GITHUB_USERNAME"
    echo ""
    echo "Example: ./github-setup.sh aryan"
    echo ""
    echo "Make sure you've created the 'DeepCompanion' repository on GitHub first!"
    echo "Visit: https://github.com/new"
    exit 1
fi

GITHUB_USERNAME="$1"
REPO_URL="https://github.com/${GITHUB_USERNAME}/DeepCompanion.git"

echo "Setting up GitHub remote connection..."
echo "Repository URL: $REPO_URL"

# Check if remote origin already exists
if git remote | grep -q "origin"; then
    echo "Removing existing origin remote..."
    git remote remove origin
fi

# Add remote origin
echo "Adding remote origin..."
git remote add origin "$REPO_URL"

# Verify remote was added
echo "Verifying remote configuration..."
git remote -v

# Push to GitHub
echo "Pushing to GitHub..."
if git push -u origin main; then
    echo ""
    echo "✅ SUCCESS! Repository successfully uploaded to GitHub!"
    echo "🌐 Your project is now available at: https://github.com/${GITHUB_USERNAME}/DeepCompanion"
    echo ""
    echo "Next steps:"
    echo "1. Visit your repository to see your code"
    echo "2. Use './workflow.sh sync' for quick updates"
    echo "3. Use './workflow.sh commit \"message\"' for custom commits"
else
    echo ""
    echo "❌ ERROR: Failed to push to GitHub"
    echo "Common fixes:"
    echo "1. Make sure you created the repository on GitHub"
    echo "2. Check your GitHub username is correct"
    echo "3. Ensure you have push permissions"
    echo "4. Try: git push -u origin main"
fi
