"""
Vercel API Entry Point for Companion AI Framework
This file serves as the main entry point for Vercel deployment
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the unified FastAPI application
from companion_baas.api.api_server import app

# Vercel expects the FastAPI app to be named 'app'
# The app variable is already defined in api_server.py

# For Vercel, we need to handle the ASGI application
application = app

if __name__ == "__main__":
    # This won't run on Vercel, but allows local testing
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)