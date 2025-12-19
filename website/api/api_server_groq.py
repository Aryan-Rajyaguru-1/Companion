#!/usr/bin/env python3
"""
Companion Brain API Server - Groq Version
==========================================

Lightweight API server using only Groq API
Perfect for Railway deployment with minimal dependencies

Deploy with these environment variables:
- API_KEY=your-secret-key
- GROQ_API_KEY=your-groq-key
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import time
import logging
from groq import Groq

# Configuration
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
API_KEY = os.getenv("API_KEY", "your-secret-api-key-change-this")
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
    description="AI Assistant powered by Groq",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Groq client
groq_client = None
if GROQ_API_KEY:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
        logger.info("✅ Groq client initialized successfully!")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Groq: {e}")
else:
    logger.warning("⚠️  No GROQ_API_KEY provided - API will use fallback responses")

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
def generate_groq_response(message: str, max_tokens: int = 2048, temperature: float = 0.7) -> str:
    """Generate response using Groq API"""
    if not groq_client:
        return "⚠️ Groq API not configured. Please set GROQ_API_KEY environment variable."
    
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
            model="llama-3.3-70b-versatile",  # Fast and capable
            max_tokens=max_tokens,
            temperature=temperature
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")

# Endpoints
@app.get("/")
async def root():
    return {
        "message": "Companion Brain API",
        "status": "running",
        "version": "2.0.0",
        "ai_provider": "Groq",
        "model": "llama-3.3-70b-versatile"
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "groq_configured": groq_client is not None,
        "timestamp": time.time()
    }

@app.post("/api/think", response_model=ThinkResponse, dependencies=[Depends(verify_api_key)])
async def think(request: ThinkRequest):
    """Main AI endpoint"""
    start_time = time.time()
    
    try:
        response = generate_groq_response(
            request.message,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )
        processing_time = time.time() - start_time
        
        return ThinkResponse(
            response=response,
            processing_time=processing_time,
            model_used="llama-3.3-70b-versatile",
            success=True
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in think endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats", dependencies=[Depends(verify_api_key)])
async def stats():
    return {
        "api_version": "2.0.0",
        "ai_provider": "Groq",
        "model": "llama-3.3-70b-versatile",
        "status": "operational"
    }

@app.get("/api/models", dependencies=[Depends(verify_api_key)])
async def list_models():
    """List available models"""
    return {
        "models": [
            {
                "id": "llama-3.3-70b-versatile",
                "name": "Llama 3.3 70B Versatile",
                "provider": "Groq",
                "description": "Fast and capable general-purpose model"
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    logger.info(f"🚀 Starting Companion Brain API on {HOST}:{PORT}")
    logger.info(f"🔑 API Key configured: {'Yes' if API_KEY != 'your-secret-api-key-change-this' else 'No (using default)'}")
    logger.info(f"🤖 Groq API configured: {'Yes' if groq_client else 'No'}")
    uvicorn.run(app, host=HOST, port=PORT)
