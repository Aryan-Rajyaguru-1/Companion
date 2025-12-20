#!/usr/bin/env python3
"""
Unified Companion Brain API Server
===================================

Single API server with provider selection:
- groq: Uses Groq API
- minimal: Uses local brain with fallback
- local: Uses companion_baas brain

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

# Set up basic logging for import errors
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import unified chat controller
try:
    from ..core.chat_controller import chat_controller
except ImportError:
    # Fallback for direct execution or when modules aren't available
    try:
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        from core.chat_controller import chat_controller
    except ImportError as e:
        logger.error(f"Failed to import chat controller: {e}")
        # Create a minimal fallback
        from typing import Dict, List, Optional, Any
        import asyncio
        import json
        import uuid
        import time

        class MinimalChatController:
            def __init__(self):
                self.agents = {"groq": self._get_groq_agent(), "minimal": self._get_minimal_agent()}

            def _get_groq_agent(self):
                try:
                    from groq import Groq
                    import os
                    api_key = os.getenv("GROQ_API_KEY")
                    if not api_key:
                        raise ValueError("GROQ_API_KEY not set")
                    client = Groq(api_key=api_key)
                    def groq_agent(message: str, **kwargs):
                        response = client.chat.completions.create(
                            messages=[{"role": "system", "content": "You are Companion Brain, an intelligent AI assistant."},
                                     {"role": "user", "content": message}],
                            model="llama-3.3-70b-versatile",
                            max_tokens=kwargs.get('max_tokens', 2048),
                            temperature=kwargs.get('temperature', 0.7)
                        )
                        return response.choices[0].message.content
                    return groq_agent
                except Exception as e:
                    logger.error(f"Failed to initialize Groq agent: {e}")
                    return self._get_minimal_agent()

            def _get_minimal_agent(self):
                def minimal_agent(message: str, **kwargs):
                    return f"Hello! I received: '{message}'. Configure a proper agent for full functionality."
                return minimal_agent

            def send_message(self, conversation_id: str, message: str, agent: str = "minimal", **kwargs):
                from datetime import datetime
                agent_func = self.agents.get(agent, self.agents["minimal"])
                response_content = agent_func(message, **kwargs)
                class Message:
                    def __init__(self, content):
                        self.content = content
                        self.agent = agent
                        self.timestamp = datetime.utcnow().isoformat()
                        self.metadata = {}
                    def to_dict(self):
                        return {
                            "id": str(uuid.uuid4()),
                            "role": "assistant",
                            "type": "text",
                            "content": self.content,
                            "agent": self.agent,
                            "timestamp": self.timestamp,
                            "metadata": self.metadata
                        }
                return Message(response_content)

            def list_conversations(self):
                return []

        chat_controller = MinimalChatController()
        logger.info("Using minimal chat controller fallback")

# Configuration
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
API_KEY = os.getenv("API_KEY", "your-secret-api-key-change-this")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Initialize FastAPI
app = FastAPI(
    title="Companion Brain API",
    description="Professional-grade AI Assistant API with unified chat management",
    version="4.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response Models
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    agent: Optional[str] = "companion"  # companion, groq, minimal
    stream: Optional[bool] = False
    max_tokens: Optional[int] = 2048
    temperature: Optional[float] = 0.7

class MessageResponse(BaseModel):
    id: str
    role: str
    type: str
    content: str
    agent: Optional[str] = None
    timestamp: str
    metadata: Optional[Dict[str, Any]] = {}

class ConversationResponse(BaseModel):
    conversation_id: str
    messages: List[Dict[str, Any]]
    created_at: str
    updated_at: str

class ConversationSummary(BaseModel):
    id: str
    message_count: int
    created_at: str
    updated_at: str

class CreateConversationResponse(BaseModel):
    conversation_id: str

# Authentication
async def verify_api_key(x_api_key: str = Header(None)):
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True

# API Endpoints
@app.get("/")
async def root():
    return {
        "message": "Companion Brain API Server",
        "version": "4.0.0",
        "description": "Professional-grade AI Assistant API with unified chat management",
        "status": "running",
        "agents": list(chat_controller.agents.keys())
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "4.0.0",
        "agents_available": list(chat_controller.agents.keys())
    }

@app.post("/chat", response_model=MessageResponse)
async def chat(request: ChatRequest, authenticated: bool = Depends(verify_api_key)):
    """Send a chat message and get response"""
    try:
        # Create conversation if not provided
        conversation_id = request.conversation_id
        if not conversation_id:
            conversation_id = chat_controller.create_conversation()

        # Send message through chat controller
        response_message = chat_controller.send_message(
            conversation_id=conversation_id,
            message=request.message,
            agent=request.agent,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )

        return MessageResponse(**response_message.to_dict())
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, authenticated: bool = Depends(verify_api_key)):
    """Stream a chat response"""
    try:
        # Create conversation if not provided
        conversation_id = request.conversation_id
        if not conversation_id:
            conversation_id = chat_controller.create_conversation()

        return StreamingResponse(
            stream_chat_response(
                conversation_id=conversation_id,
                message=request.message,
                agent=request.agent,
                max_tokens=request.max_tokens,
                temperature=request.temperature
            ),
            media_type="text/plain"
        )
    except Exception as e:
        logger.error(f"Stream chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Stream chat error: {str(e)}")

async def stream_chat_response(conversation_id: str, message: str, agent: str = "companion",
                              max_tokens: int = 2048, temperature: float = 0.7):
    """Stream chat response from chat controller"""
    try:
        # Send message through chat controller
        response_message = chat_controller.send_message(
            conversation_id=conversation_id,
            message=message,
            agent=agent,
            max_tokens=max_tokens,
            temperature=temperature
        )

        # Stream the response content word by word
        words = response_message.content.split()
        current_content = ""

        for word in words:
            current_content += word + " "
            streamed_message = response_message.to_dict()
            streamed_message["content"] = current_content.strip()

            yield f"data: {json.dumps(streamed_message)}\n\n"
            await asyncio.sleep(0.05)  # Small delay for streaming effect

        # Send completion signal
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        logger.error(f"Streaming error: {e}")
        error_message = {
            "id": str(uuid.uuid4()),
            "role": "system",
            "type": "error",
            "content": f"Streaming error: {str(e)}",
            "timestamp": time.time(),
            "agent": agent
        }
@app.get("/conversations")
async def get_conversations(authenticated: bool = Depends(verify_api_key)):
    """Get all conversations"""
    try:
        conversations = chat_controller.list_conversations()
        return {"conversations": conversations}
    except Exception as e:
        logger.error(f"Get conversations error: {e}")
        raise HTTPException(status_code=500, detail=f"Get conversations error: {str(e)}")

@app.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: str, authenticated: bool = Depends(verify_api_key)):
    """Get a specific conversation with message history"""
    try:
        conversation = chat_controller.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return ConversationResponse(
            conversation_id=conversation_id,
            messages=conversation.get_messages(),
            created_at=conversation.created_at,
            updated_at=conversation.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get conversation error: {e}")
        raise HTTPException(status_code=500, detail=f"Get conversation error: {str(e)}")

@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, authenticated: bool = Depends(verify_api_key)):
    """Delete a conversation"""
    try:
        success = chat_controller.delete_conversation(conversation_id)
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return {"message": "Conversation deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete conversation error: {e}")
        raise HTTPException(status_code=500, detail=f"Delete conversation error: {str(e)}")

@app.post("/conversations", response_model=CreateConversationResponse)
async def create_conversation(authenticated: bool = Depends(verify_api_key)):
    """Create a new conversation"""
    try:
        conversation_id = chat_controller.create_conversation()
        return CreateConversationResponse(conversation_id=conversation_id)
    except Exception as e:
        logger.error(f"Create conversation error: {e}")
        raise HTTPException(status_code=500, detail=f"Create conversation error: {str(e)}")
if __name__ == "__main__":
    import uvicorn
    logger.info(f"🚀 Starting Companion Brain API Server v4.0.0 on {HOST}:{PORT}")
    logger.info(f"Available agents: {list(chat_controller.agents.keys())}")
    uvicorn.run(app, host=HOST, port=PORT)
