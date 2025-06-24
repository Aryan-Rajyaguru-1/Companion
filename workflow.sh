#!/bin/bash

# DeepCompanion Development Workflow
# Quick commands for managing your GitHub repository

case "$1" in
    "sync")
        echo "Syncing with GitHub..."
        git add .
        git commit -m "Update: $(date '+%Y-%m-%d %H:%M')"
        git push origin main
        echo "✅ Changes pushed to GitHub"
        ;;
    "pull")
        echo "Pulling latest changes from GitHub..."
        git pull origin main
        echo "✅ Repository updated"
        ;;
    "status")
        echo "Repository status:"
        git status --porcelain
        echo ""
        echo "Recent commits:"
        git log --oneline -5
        ;;
    "commit")
        if [ -z "$2" ]; then
            echo "Usage: ./workflow.sh commit \"Your commit message\""
            exit 1
        fi
        git add .
        git commit -m "$2"
        git push origin main
        echo "✅ Committed and pushed: $2"
        ;;
    *)
        echo "DeepCompanion Development Workflow"
        echo ""
        echo "Usage: ./workflow.sh [command]"
        echo ""
        echo "Commands:"
        echo "  sync     - Quick sync (commit with timestamp and push)"
        echo "  pull     - Pull latest changes from GitHub"
        echo "  status   - Show repository status and recent commits"
        echo "  commit   - Commit with custom message and push"
        echo ""
        echo "Examples:"
        echo "  ./workflow.sh sync"
        echo "  ./workflow.sh commit \"Added new feature\""
        echo "  ./workflow.sh pull"
        ;;
esac
