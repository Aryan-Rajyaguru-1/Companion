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
from typing import Optional, Dict, Any
import os
import time
import logging
import asyncio
import json
import uuid

# Import database
try:
    from ..core.database import db
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from core.database import db

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

# Initialize FastAPI
app = FastAPI(
    title="Companion Brain API",
    description=f"AI Assistant powered by {PROVIDER}",
    version="3.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize clients based on provider
groq_client = None
if PROVIDER == "groq" and GROQ_API_KEY:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
        logger.info("✅ Groq client initialized successfully!")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Groq: {e}")
elif PROVIDER == "groq":
    logger.warning("⚠️  PROVIDER=groq but no GROQ_API_KEY - will use fallback")

# Conversation storage now handled by database
# conversations = {}

# Request/Response Models
class ThinkRequest(BaseModel):
    message: str
    use_agi: Optional[bool] = True
    max_tokens: Optional[int] = 2048
    temperature: Optional[float] = 0.7

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    stream: Optional[bool] = False

class ConversationResponse(BaseModel):
    conversation_id: str
    messages: list
    created_at: str

class MessageResponse(BaseModel):
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

# AI Response Generator
def generate_response(message: str, max_tokens: int = 2048, temperature: float = 0.7) -> str:
    """Generate response based on provider"""
    
    if PROVIDER == "groq" and groq_client:
        return generate_groq_response(message, max_tokens, temperature)
    elif PROVIDER == "local":
        return generate_local_response(message, max_tokens, temperature)
    else:  # minimal or fallback
        return generate_minimal_response(message, max_tokens, temperature)

def generate_groq_response(message: str, max_tokens: int = 2048, temperature: float = 0.7) -> str:
    """Generate response using Groq API"""
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are Companion Brain, an intelligent AI assistant. Provide helpful, accurate, and friendly responses."
                },
                {
                    "role": "user",
                    "content": message
                }
            ],
            model="llama-3.3-70b-versatile",
            max_tokens=max_tokens,
            temperature=temperature
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return f"⚠️ Groq API error: {str(e)}"

def generate_local_response(message: str, max_tokens: int = 2048, temperature: float = 0.7) -> str:
    """Generate response using local companion_baas brain"""
    try:
        # Import and use local brain
        from companion_baas.core.brain import Brain
        
        brain = Brain()
        response = brain.think(message, use_agi=True)
        return response.get('response', 'Local brain response unavailable')
    except Exception as e:
        logger.error(f"Local brain error: {e}")
        return f"⚠️ Local brain error: {str(e)}"

def generate_minimal_response(message: str, max_tokens: int = 2048, temperature: float = 0.7) -> str:
    """Generate minimal fallback response"""
    return f"Hello! I received your message: '{message}'. This is a minimal response - configure a proper provider for full functionality."

# API Endpoints
@app.get("/")
async def root():
    return {
        "message": "Companion Brain API Server",
        "version": "3.0.0",
        "provider": PROVIDER,
        "status": "running"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "provider": PROVIDER}

@app.post("/chat", response_model=MessageResponse)
async def chat(request: ChatRequest, authenticated: bool = Depends(verify_api_key)):
    conversation_id = request.conversation_id or f"conv_{int(time.time())}"
    
    # Initialize conversation if it doesn't exist
    conversation = db.get_conversation(conversation_id)
    if not conversation:
        db.create_conversation(conversation_id)
    
    # Add user message
    user_message = {
        "id": str(uuid.uuid4()),
        "role": "user",
        "type": "user",
        "content": request.message,
        "timestamp": str(time.time())
    }
    db.add_message(conversation_id, user_message)
    
    # Generate response
    try:
        response_content = generate_response(request.message)
        
        ai_message = {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "type": "assistant",
            "content": response_content,
            "timestamp": str(time.time())
        }
        db.add_message(conversation_id, ai_message)
        
        return MessageResponse(**ai_message)
    except Exception as e:
        error_message = {
            "id": str(uuid.uuid4()),
            "role": "system",
            "type": "error",
            "content": f"Error: {str(e)}",
            "timestamp": str(time.time())
        }
        db.add_message(conversation_id, error_message)
        return MessageResponse(**error_message)

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, authenticated: bool = Depends(verify_api_key)):
    conversation_id = request.conversation_id or f"conv_{int(time.time())}"
    
    # Initialize conversation if it doesn't exist
    conversation = db.get_conversation(conversation_id)
    if not conversation:
        db.create_conversation(conversation_id)
    
    # Add user message
    user_message = {
        "id": str(uuid.uuid4()),
        "role": "user",
        "type": "user",
        "content": request.message,
        "timestamp": str(time.time())
    }
    db.add_message(conversation_id, user_message)
    
    return StreamingResponse(
        stream_response(request.message, conversation_id),
        media_type="text/plain"
    )

async def stream_response(message: str, conversation_id: str):
    """Stream the AI response"""
    try:
        # Simulate streaming by yielding chunks
        response_text = generate_response(message)
        
        # Split response into chunks for streaming effect
        words = response_text.split()
        ai_message = {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "type": "assistant",
            "content": "",
            "timestamp": str(time.time())
        }
        
        for i, word in enumerate(words):
            ai_message["content"] += word + " "
            
            # Yield the current message state
            yield f"data: {json.dumps(ai_message)}\n\n"
            
            # Small delay for streaming effect
            await asyncio.sleep(0.05)
        
        # Add final message to conversation
        db.add_message(conversation_id, ai_message)
        
        # Send completion signal
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        
    except Exception as e:
        error_message = {
            "id": str(uuid.uuid4()),
            "role": "system",
            "type": "error",
            "content": f"Error: {str(e)}",
            "timestamp": str(time.time())
        }
        db.add_message(conversation_id, error_message)
        yield f"data: {json.dumps(error_message)}\n\n"

@app.get("/conversations")
async def get_conversations(authenticated: bool = Depends(verify_api_key)):
    conversations = db.get_all_conversations()
    return {
        "conversations": [
            {
                "id": conv["id"],
                "message_count": conv["message_count"],
                "created_at": conv["created_at"],
                "updated_at": conv["updated_at"]
            }
            for conv in conversations
        ]
    }

@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, authenticated: bool = Depends(verify_api_key)):
    conversation = db.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return ConversationResponse(
        conversation_id=conversation_id,
        messages=conversation["messages"],
        created_at=conversation["created_at"]
    )

@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, authenticated: bool = Depends(verify_api_key)):
    conversation = db.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    db.delete_conversation(conversation_id)
    return {"message": "Conversation deleted"}

@app.post("/conversations")
async def create_conversation(authenticated: bool = Depends(verify_api_key)):
    conversation_id = f"conv_{int(time.time())}"
    db.create_conversation(conversation_id)
    return {"conversation_id": conversation_id}

if __name__ == "__main__":
    import uvicorn
    logger.info(f"🚀 Starting Companion Brain API Server on {HOST}:{PORT} with provider: {PROVIDER}")
    uvicorn.run(app, host=HOST, port=PORT)
