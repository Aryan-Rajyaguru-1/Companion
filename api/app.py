"""
Vercel API Entry Point for Companion AI Framework
This file serves as the main entry point for Vercel deployment
"""

import os
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import json
import time

# Add companion_baas to path for brain imports
current_dir = Path(__file__).parent
baas_dir = current_dir.parent / "companion_baas"
sys.path.insert(0, str(baas_dir))

# Import the real brain
try:
    from sdk.client import Brain
    BRAIN_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Brain not available: {e}")
    BRAIN_AVAILABLE = False

# Vercel-compatible FastAPI app
app = FastAPI(title="Companion AI API", version="1.0.0")

# Global brain instance (lazy initialization for Vercel)
brain_instance = None

def get_brain():
    """Lazy initialization of brain for Vercel cold starts"""
    global brain_instance
    if brain_instance is None and BRAIN_AVAILABLE:
        try:
            print("🚀 Initializing Companion Brain...")
            brain_instance = Brain(app_type="chatbot", enable_agi=True)
            print("✅ Brain initialized successfully")
        except Exception as e:
            print(f"❌ Failed to initialize brain: {e}")
            brain_instance = None
    return brain_instance

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class ChatRequest(BaseModel):
    message: str
    conversation_id: str

class MessageResponse(BaseModel):
    role: str
    content: str
    type: str
    id: str
    conversation_id: str
    timestamp: str

class ChatResponse(BaseModel):
    message: MessageResponse
    conversation_id: str

# Simple in-memory storage for Vercel (no database)
conversations = {}

# API Key authentication
API_KEY = os.getenv("COMPANION_API_KEY", "your-secret-api-key-change-this")

async def verify_api_key(x_api_key: str = Header(None)):
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "version": "1.0.0"}

@app.post("/v1/chat", response_model=ChatResponse)
async def chat_v1(request: ChatRequest, x_api_key: str = Header(None)):
    """Unified chat endpoint with real brain integration"""
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    message = request.message
    conversation_id = request.conversation_id or "default"

    # Get brain instance
    brain = get_brain()
    if not brain:
        # Fallback to simple response if brain not available
        content = "I'm sorry, the brain is currently unavailable. Please try again later."
        response_type = "error"
    else:
        try:
            # Use real brain for response
            result = brain.chat(
                message=message,
                conversation_id=conversation_id,
                user_id="vercel_user"  # Default user for Vercel
            )
            content = result.get('response', 'I apologize, but I could not generate a response.')
            response_type = "assistant"
        except Exception as e:
            print(f"Brain error: {e}")
            content = "I encountered an error while processing your request. Please try again."
            response_type = "error"

    # Create response
    import uuid
    from datetime import datetime

    message_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat() + "Z"

    response = {
        "message": {
            "role": "assistant",
            "content": content,
            "type": response_type,
            "id": message_id,
            "conversation_id": conversation_id,
            "timestamp": timestamp
        },
        "conversation_id": conversation_id
    }

    return response
    return {
        "message": {
            "role": "assistant",
            "content": content,
            "type": "assistant",
            "id": message_id,
            "conversation_id": conversation_id,
            "timestamp": timestamp
        },
        "conversation_id": conversation_id
    }

@app.get("/v1/conversations")
async def get_conversations(x_api_key: str = Header(None)):
    """Get conversations (simplified for Vercel)"""
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    # Return empty list for Vercel compatibility
    return []

# ============================================================================
# Authentication endpoints (simplified for Vercel)
# ============================================================================

@app.post("/api/auth/register")
async def register():
    """Simplified registration endpoint"""
    # For Vercel, just return success
    return {"success": True, "message": "Registration successful"}

@app.post("/api/auth/login")
async def login():
    """Simplified login endpoint"""
    # For Vercel, just return success with a dummy token
    return {
        "success": True,
        "token": "vercel-demo-token",
        "user": {
            "id": 1,
            "email": "demo@companion.ai",
            "name": "Demo User"
        }
    }

@app.get("/api/auth/me")
async def get_me():
    """Get current user info"""
    # For Vercel, return demo user
    return {
        "success": True,
        "user": {
            "id": 1,
            "email": "demo@companion.ai",
            "name": "Demo User"
        }
    }

@app.post("/api/auth/change-password")
async def change_password():
    """Change password endpoint"""
    return {"success": True, "message": "Password changed successfully"}

# ============================================================================
# Static file serving for frontend
# ============================================================================

@app.get("/")
async def serve_index():
    """Serve the main index page"""
    frontend_path = Path(__file__).parent.parent / "website" / "frontend" / "index.html"
    if frontend_path.exists():
        return FileResponse(frontend_path, media_type="text/html")
    return {"error": "Frontend not found"}

@app.get("/chat")
async def serve_chat():
    """Serve the chat interface"""
    frontend_path = Path(__file__).parent.parent / "website" / "frontend" / "modern-demo.html"
    if frontend_path.exists():
        return FileResponse(frontend_path, media_type="text/html")
    return {"error": "Chat page not found"}

@app.get("/home")
async def serve_home():
    """Serve the home page"""
    frontend_path = Path(__file__).parent.parent / "website" / "frontend" / "index.html"
    if frontend_path.exists():
        return FileResponse(frontend_path, media_type="text/html")
    return {"error": "Home page not found"}

@app.get("/{path:path}")
async def serve_static(path: str):
    """Serve static files from frontend directory"""
    if path.startswith("api/"):
        # Don't serve API paths as static files
        raise HTTPException(status_code=404, detail="Not found")

    frontend_path = Path(__file__).parent.parent / "website" / "frontend" / path
    if frontend_path.exists() and frontend_path.is_file():
        # Determine media type based on file extension
        if path.endswith('.html'):
            media_type = "text/html"
        elif path.endswith('.css'):
            media_type = "text/css"
        elif path.endswith('.js'):
            media_type = "application/javascript"
        elif path.endswith('.png'):
            media_type = "image/png"
        elif path.endswith('.svg'):
            media_type = "image/svg+xml"
        else:
            media_type = "application/octet-stream"

        return FileResponse(frontend_path, media_type=media_type)

    # Fallback to index.html for SPA routing
    index_path = Path(__file__).parent.parent / "website" / "frontend" / "index.html"
    if index_path.exists():
        return FileResponse(index_path, media_type="text/html")

    raise HTTPException(status_code=404, detail="File not found")

# Vercel expects the FastAPI app to be named 'app'
# For Vercel, we need to handle the ASGI application
application = app

if __name__ == "__main__":
    # This won't run on Vercel, but allows local testing
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)