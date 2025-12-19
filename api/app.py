"""
Vercel API Entry Point for Companion AI Framework
This file serves as the main entry point for Vercel deployment
"""

import os
import sys
from pathlib import Path

# Add the api directory to Python path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent))

# Import the main Flask application
from chat_backend_baas import app

# Vercel expects the Flask app to be named 'app'
# The app variable is already defined in chat_backend_baas.py

# For Vercel, we need to handle the WSGI application
application = app

if __name__ == "__main__":
    # This won't run on Vercel, but allows local testing
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)