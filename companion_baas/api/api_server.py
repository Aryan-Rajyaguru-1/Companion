#!/usr/bin/env python3
"""
Unified Companion Brain API Server v1.0.0
==========================================

Single API server with versioned endpoints, chat controller, and agent routing.
Professional-grade API with strict contracts and clear separation of concerns.

Environment variables:
- API_KEY: Your secret API key
- PROVIDER: groq | minimal | local (default: groq)
- GROQ_API_KEY: Required for groq provider
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import os
import time
import logging
import asyncio
import json
import uuid

# Import our components
try:
    from companion_baas.api.controllers.chat_controller import ChatController
    from companion_baas.api.schemas.message import MessageCreate, MessageResponse, StreamingMessage
    from companion_baas.api.schemas.conversation import ConversationCreate, ConversationResponse, ConversationListItem
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.error(f"Failed to import API components: {e}")
    # Define dummy classes for Vercel deployment
    class ChatController:
        def __init__(self): pass
        async def process_message(self, message, conversation_id, user_id=None): 
            return {"message": {"content": "API not available", "role": "assistant", "type": "assistant", "id": "error", "conversation_id": conversation_id, "timestamp": "2025-01-01T00:00:00Z"}, "conversation_id": conversation_id}
    
    class MessageCreate: pass
    class MessageResponse: pass
    class StreamingMessage: pass
    class ConversationCreate: pass
    class ConversationResponse: pass
    class ConversationListItem: pass

# Import database
try:
    from companion_baas.core.database import db
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.error(f"Failed to import database: {e}")
    # Define dummy database for Vercel deployment
    class DummyDB:
        def get_conversation(self, cid): return None
        def create_conversation(self, cid): pass
        def get_all_conversations(self): return []
        def add_message(self, cid, msg): return {"id": "error", "role": "system", "type": "error", "content": "Database not available", "timestamp": "2025-01-01T00:00:00Z"}
    db = DummyDB()

# Configuration
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
API_KEY = os.getenv("API_KEY", "your-secret-api-key-change-this")
PROVIDER = os.getenv("PROVIDER", "groq").lower()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI with versioning
app = FastAPI(
    title="Companion Brain API",
    description="Professional AI assistant with agent routing and conversation management",
    version="1.0.0",
    docs_url="/v1/docs",
    redoc_url="/v1/redoc",
    openapi_url="/v1/openapi.json"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Chat Controller
chat_controller = ChatController()

# Request/Response Models (Legacy - kept for backward compatibility)
class ThinkRequest(BaseModel):
    message: str
    use_agi: Optional[bool] = True
    max_tokens: Optional[int] = 2048
    temperature: Optional[float] = 0.7

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    stream: Optional[bool] = False

class ConversationResponseLegacy(BaseModel):
    conversation_id: str
    messages: list
    created_at: str

class MessageResponseLegacy(BaseModel):
    id: str
    role: str
    type: str
    content: str
    agent: Optional[str] = None
    timestamp: str

class ThinkResponse(BaseModel):
    response: str
    processing_time: float
    model_used: str
    success: bool

# Authentication
async def verify_api_key(x_api_key: str = Header(None)):
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True

# Legacy AI Response Generator (kept for backward compatibility)
def generate_response(message: str, max_tokens: int = 2048, temperature: float = 0.7) -> str:
    """Legacy response generator - use ChatController instead"""
    try:
        # Simple fallback response
        return f"Hello! I received your message: '{message}'. Please use the v1 API endpoints for full functionality."
    except Exception as e:
        logger.error(f"Legacy response error: {e}")
        return f"⚠️ Error: {str(e)}"

# API Endpoints

# Root endpoints
@app.get("/")
async def root():
    return {
        "message": "Companion Brain API Server",
        "version": "1.0.0",
        "status": "running",
        "docs": "/v1/docs"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}

# Legacy endpoints (deprecated - use /v1/ endpoints)
@app.post("/chat", response_model=MessageResponseLegacy)
async def chat_legacy(request: ChatRequest, authenticated: bool = Depends(verify_api_key)):
    """Legacy chat endpoint - use /v1/chat instead"""
    result = await chat_controller.process_message(
        message=request.message,
        conversation_id=request.conversation_id,
        stream=False
    )

    # Convert to legacy format
    return MessageResponseLegacy(**result["message"].dict())

@app.post("/chat/stream")
async def chat_stream_legacy(request: ChatRequest, authenticated: bool = Depends(verify_api_key)):
    """Legacy streaming endpoint - use /v1/chat/stream instead"""
    result = await chat_controller.process_message(
        message=request.message,
        conversation_id=request.conversation_id,
        stream=True
    )

    async def stream_generator():
        async for chunk in result["stream_generator"]():
            yield f"data: {json.dumps(chunk)}\n\n"

    return StreamingResponse(
        stream_generator(),
        media_type="text/plain"
    )

# Version 1 API endpoints
@app.post("/v1/chat", response_model=MessageResponse)
async def chat_v1(request: ChatRequest, authenticated: bool = Depends(verify_api_key)):
    """Send a chat message and get AI response with agent routing"""
    result = await chat_controller.process_message(
        message=request.message,
        conversation_id=request.conversation_id,
        stream=False
    )

    return result["message"]

@app.post("/v1/chat/stream")
async def chat_stream_v1(request: ChatRequest, authenticated: bool = Depends(verify_api_key)):
    """Stream a chat response with real-time updates"""
    result = await chat_controller.process_message(
        message=request.message,
        conversation_id=request.conversation_id,
        stream=True
    )

    async def stream_generator():
        async for chunk in result["stream_generator"]():
            yield f"data: {json.dumps(chunk)}\n\n"

    return StreamingResponse(
        stream_generator(),
        media_type="text/plain",
        headers={"Content-Type": "text/event-stream"}
    )

@app.get("/v1/conversations", response_model=List[ConversationListItem])
async def get_conversations_v1(authenticated: bool = Depends(verify_api_key)):
    """Get list of conversations"""
    conversations = chat_controller.get_conversations()

    return [
        ConversationListItem(
            conversation_id=conv["id"],
            title=conv.get("title", f"Conversation {conv['id'][:8]}"),
            message_count=conv["message_count"],
            created_at=conv["created_at"],
            updated_at=conv.get("updated_at", conv["created_at"]),
            last_agent=conv.get("metadata", {}).get("last_agent"),
            metadata=conv.get("metadata", {})
        )
        for conv in conversations
    ]

@app.post("/v1/conversations", response_model=ConversationResponse)
async def create_conversation_v1(request: ConversationCreate, authenticated: bool = Depends(verify_api_key)):
    """Create a new conversation"""
    conversation_id = f"conv_{int(time.time())}_{str(uuid.uuid4())[:8]}"
    db.create_conversation(conversation_id)

    return ConversationResponse(
        conversation_id=conversation_id,
        title=request.title,
        messages=[],
        created_at=str(time.time()),
        updated_at=str(time.time()),
        user_id=None  # TODO: Add user authentication
    )

@app.get("/v1/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation_v1(conversation_id: str, authenticated: bool = Depends(verify_api_key)):
    """Get a specific conversation with all messages"""
    conversation = chat_controller.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return conversation

@app.delete("/v1/conversations/{conversation_id}")
async def delete_conversation_v1(conversation_id: str, authenticated: bool = Depends(verify_api_key)):
    """Delete a conversation"""
    success = chat_controller.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {"message": "Conversation deleted"}

@app.get("/v1/agents")
async def get_agents_v1(authenticated: bool = Depends(verify_api_key)):
    """Get information about available agents"""
    from .routers.agent_router import AgentRouter
    router = AgentRouter()

    agents_info = []
    for agent_name in router.get_available_agents():
        agent_info = router.get_agent_info(agent_name)
        if agent_info:
            agents_info.append(agent_info)

    return {"agents": agents_info}

# Legacy endpoints for backward compatibility
@app.get("/conversations")
async def get_conversations_legacy(authenticated: bool = Depends(verify_api_key)):
    """Legacy conversations endpoint"""
    conversations = chat_controller.get_conversations()
    return {
        "conversations": [
            {
                "id": conv["id"],
                "message_count": conv["message_count"],
                "created_at": conv["created_at"],
                "updated_at": conv.get("updated_at", conv["created_at"])
            }
            for conv in conversations
        ]
    }

@app.get("/conversations/{conversation_id}")
async def get_conversation_legacy(conversation_id: str, authenticated: bool = Depends(verify_api_key)):
    """Legacy conversation endpoint"""
    conversation = chat_controller.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationResponseLegacy(
        conversation_id=conversation_id,
        messages=conversation.messages,
        created_at=conversation.created_at
    )

@app.delete("/conversations/{conversation_id}")
async def delete_conversation_legacy(conversation_id: str, authenticated: bool = Depends(verify_api_key)):
    """Legacy delete conversation endpoint"""
    success = chat_controller.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {"message": "Conversation deleted"}

@app.post("/conversations")
async def create_conversation_legacy(authenticated: bool = Depends(verify_api_key)):
    """Legacy create conversation endpoint"""
    conversation_id = f"conv_{int(time.time())}"
    db.create_conversation(conversation_id)
    return {"conversation_id": conversation_id}

if __name__ == "__main__":
    import uvicorn
    logger.info(f"🚀 Starting Companion Brain API Server v1.0.0 on {HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)
