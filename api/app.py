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

# Vercel-compatible FastAPI app
app = FastAPI(title="Companion AI API", version="1.0.0")

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
API_KEY = os.getenv("API_KEY", "your-secret-api-key-change-this")

async def verify_api_key(x_api_key: str = Header(None)):
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "version": "1.0.0"}

@app.post("/v1/chat", response_model=ChatResponse)
async def chat_v1(request: ChatRequest):  # x_api_key: str = Header(None)
    """Unified chat endpoint with agent routing"""
    # Temporarily disable auth for testing
    # if not x_api_key or x_api_key != API_KEY:
    #     raise HTTPException(status_code=401, detail="Invalid or missing API key")

    # Simple agent routing based on keywords
    message_lower = request.message.lower()
    agent = "general"

    if any(keyword in message_lower for keyword in ["code", "function", "python", "javascript", "program"]):
        agent = "code"
    elif any(keyword in message_lower for keyword in ["research", "find", "search", "information"]):
        agent = "research"
    elif any(keyword in message_lower for keyword in ["review", "check", "analyze", "test"]):
        agent = "review"

    # Generate response based on agent
    if agent == "code":
        content = f"I understand you need help with coding. Here's a simple Python example:\n\n```python\ndef fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)\n\n# Example usage\nfor i in range(10):\n    print(f'F({i}) = {fibonacci(i)}')\n```"
    elif agent == "research":
        content = "I can help you research topics. For Vercel deployment, I'm running in a serverless environment with limited access to external resources. Please provide more specific details about what you'd like to research."
    elif agent == "review":
        content = "I'll help you review your code. Please share the specific code you'd like me to analyze, and I'll provide feedback on potential improvements, bugs, or best practices."
    else:
        content = f"Hello! I'm your Companion AI assistant. I detected that your message might be best handled by our {agent} agent. How can I help you today?"

    # Create response
    import uuid
    from datetime import datetime

    message_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat() + "Z"

    response = ChatResponse(
        message=MessageResponse(
            role="assistant",
            content=content,
            type="assistant",
            id=message_id,
            conversation_id=request.conversation_id,
            timestamp=timestamp
        ),
        conversation_id=request.conversation_id
    )

    return response

@app.get("/v1/conversations")
async def get_conversations():  # x_api_key: str = Header(None)
    """Get conversations (simplified for Vercel)"""
    # Temporarily disable auth for testing
    # if not x_api_key or x_api_key != API_KEY:
    #     raise HTTPException(status_code=401, detail="Invalid or missing API key")

    # Return empty list for Vercel compatibility
    return []

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