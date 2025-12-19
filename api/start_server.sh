#!/bin/bash
# Start the Companion AI API server with virtual environment

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Activate virtual environment
source "$PROJECT_DIR/.venv/bin/activate"

# Change to API directory
cd "$SCRIPT_DIR"

# Set environment variables
export FLASK_APP=app.py
export FLASK_ENV=development
export PYTHONPATH="$SCRIPT_DIR:$PROJECT_DIR"

# Start the Flask server
echo "🚀 Starting Companion AI API Server..."
echo "📍 Virtual Environment: $(which python)"
echo "🌐 Server will be available at: http://localhost:5000"
echo ""

python app.py