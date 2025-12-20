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
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os
import time
import logging
from groq import Groq

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

# Request/Response Models
class ThinkRequest(BaseModel):
    message: str
    use_agi: Optional[bool] = True
    max_tokens: Optional[int] = 2048
    temperature: Optional[float] = 0.7

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

@app.post("/think", response_model=ThinkResponse)
async def think(request: ThinkRequest, authenticated: bool = Depends(verify_api_key)):
    start_time = time.time()
    
    try:
        response = generate_response(
            request.message,
            request.max_tokens,
            request.temperature
        )
        
        processing_time = time.time() - start_time
        
        return ThinkResponse(
            response=response,
            processing_time=processing_time,
            model_used=f"{PROVIDER}-model",
            success=True
        )
    except Exception as e:
        logger.error(f"Think endpoint error: {e}")
        processing_time = time.time() - start_time
        
        return ThinkResponse(
            response=f"Error: {str(e)}",
            processing_time=processing_time,
            model_used="error",
            success=False
        )

if __name__ == "__main__":
    import uvicorn
    logger.info(f"🚀 Starting Companion Brain API Server on {HOST}:{PORT} with provider: {PROVIDER}")
    uvicorn.run(app, host=HOST, port=PORT)
