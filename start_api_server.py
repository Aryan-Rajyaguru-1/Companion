#!/usr/bin/env python3
"""
Startup script for the Companion Brain API Server
"""

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Now import and run the server
from companion_baas.api.api_server import app
import uvicorn

if __name__ == "__main__":
    print("🚀 Starting Companion Brain API Server v1.0.0...")
    uvicorn.run(app, host="0.0.0.0", port=8000)