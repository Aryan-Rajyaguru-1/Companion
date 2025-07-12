#!/usr/bin/env python3
"""
Companion Backend API Server
A FastAPI backend that connects the web interface to AI models (Ollama + OpenRouter)
"""

import asyncio
import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Union, AsyncGenerator
from contextlib import asynccontextmanager

# FastAPI and web framework imports
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

# HTTP clients
import httpx
import requests

# Environment and configuration
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()

# Configuration
class Config:
    # Server settings
    HOST = "0.0.0.0"
    PORT = 8001
    
    # Ollama settings
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
    
    # OpenRouter settings
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_URL = "https://openrouter.ai/api/v1"
    
    # Model configurations
    LOCAL_MODELS = {
        "chat": {
            "model": "llama3.2:3b",
            "name": "Llama 3.2 3B",
            "description": "Fast local chat model",
            "type": "local"
        },
        "think": {
            "model": "deepseek-r1:1.5b",
            "name": "DeepSeek R1 1.5B", 
            "description": "Reasoning and analysis",
            "type": "local"
        },
        "code": {
            "model": "codegemma:2b",
            "name": "CodeGemma 2B",
            "description": "Code generation and programming",
            "type": "local"
        },
        "advanced": {
            "model": "codeqwen:7b",
            "name": "CodeQwen 7B",
            "description": "Advanced coding and architecture",
            "type": "local"
        }
    }
    
    CLOUD_MODELS = {
        "deepseek-r1": {
            "model": "deepseek/deepseek-r1",
            "name": "DeepSeek R1",
            "description": "Advanced reasoning model",
            "type": "cloud"
        },
        "gpt-4o": {
            "model": "openai/gpt-4o-2024-08-06",
            "name": "GPT-4o",
            "description": "OpenAI's most advanced model",
            "type": "cloud"
        },
        "gemini-flash": {
            "model": "google/gemini-2.0-flash-exp",
            "name": "Gemini 2.0 Flash",
            "description": "Google's fast multimodal AI",
            "type": "cloud"
        }
    }

# Pydantic models for API
class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role: user, assistant, or system")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = Field(default_factory=datetime.now)

class ChatRequest(BaseModel):
    model: str = Field(..., description="Model ID to use")
    messages: List[ChatMessage] = Field(..., description="Conversation history")
    stream: bool = Field(default=True, description="Whether to stream response")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=8192)

class TestRequest(BaseModel):
    model: str = Field(..., description="Model ID to use for testing")
    prompt: str = Field(..., description="Test prompt")
    stream: bool = Field(default=False, description="Whether to stream response")

class ModelInfo(BaseModel):
    id: str
    name: str
    description: str
    type: str  # "local" or "cloud"
    available: bool = Field(default=False)

class ChatResponse(BaseModel):
    id: str
    model: str
    choices: List[Dict]
    usage: Optional[Dict] = None
    created: int = Field(default_factory=lambda: int(time.time()))

# Global state
class AppState:
    def __init__(self):
        self.ollama_available = False
        self.openrouter_available = False
        self.available_models = {}
        self.active_connections = {}

app_state = AppState()

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("🚀 Starting Companion Backend API...")
    
    # Startup: Check model availability
    await check_ollama_status()
    await check_openrouter_status()
    await refresh_available_models()
    
    logger.info("✅ Backend API ready!")
    yield
    
    # Shutdown
    logger.info("🔄 Shutting down Companion Backend API...")

# Initialize FastAPI app
app = FastAPI(
    title="Companion Backend API",
    description="Backend API for Companion AI Chat Interface",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "ollama_available": app_state.ollama_available,
        "openrouter_available": app_state.openrouter_available,
        "available_models": len(app_state.available_models)
    }

# Model management functions
async def check_ollama_status() -> bool:
    """Check if Ollama is available"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{Config.OLLAMA_URL}/api/tags")
            app_state.ollama_available = response.status_code == 200
            if app_state.ollama_available:
                logger.info("✅ Ollama is available")
            else:
                logger.warning("⚠️ Ollama is not responding")
    except Exception as e:
        app_state.ollama_available = False
        logger.warning(f"⚠️ Ollama connection failed: {e}")
    
    return app_state.ollama_available

async def check_openrouter_status() -> bool:
    """Check if OpenRouter is available"""
    if not Config.OPENROUTER_API_KEY:
        logger.warning("⚠️ OpenRouter API key not configured")
        app_state.openrouter_available = False
        return False
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            headers = {
                "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            }
            response = await client.get(f"{Config.OPENROUTER_URL}/models", headers=headers)
            app_state.openrouter_available = response.status_code == 200
            if app_state.openrouter_available:
                logger.info("✅ OpenRouter is available")
            else:
                logger.warning("⚠️ OpenRouter API key invalid or service unavailable")
    except Exception as e:
        app_state.openrouter_available = False
        logger.warning(f"⚠️ OpenRouter connection failed: {e}")
    
    return app_state.openrouter_available

async def refresh_available_models():
    """Refresh the list of available models"""
    app_state.available_models = {}
    
    # Add local models if Ollama is available
    if app_state.ollama_available:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{Config.OLLAMA_URL}/api/tags")
                if response.status_code == 200:
                    ollama_models = response.json().get("models", [])
                    installed_models = {model["name"].split(":")[0] for model in ollama_models}
                    
                    for model_id, config in Config.LOCAL_MODELS.items():
                        model_name = config["model"].split(":")[0]
                        available = model_name in installed_models
                        app_state.available_models[model_id] = ModelInfo(
                            id=model_id,
                            name=config["name"],
                            description=config["description"],
                            type="local",
                            available=available
                        )
        except Exception as e:
            logger.error(f"Error fetching Ollama models: {e}")
    
    # Add cloud models if OpenRouter is available
    if app_state.openrouter_available:
        for model_id, config in Config.CLOUD_MODELS.items():
            app_state.available_models[model_id] = ModelInfo(
                id=model_id,
                name=config["name"],
                description=config["description"],
                type="cloud",
                available=True
            )
    
    logger.info(f"📋 Available models: {len(app_state.available_models)}")

# API Endpoints

@app.get("/api/models")
async def list_models():
    """Get list of available models"""
    await refresh_available_models()
    return {
        "models": [model.dict() for model in app_state.available_models.values()],
        "count": len(app_state.available_models),
        "ollama_available": app_state.ollama_available,
        "openrouter_available": app_state.openrouter_available
    }

@app.post("/api/test")
async def test_model(request: TestRequest):
    """Test a model with a simple prompt"""
    if request.model not in app_state.available_models:
        raise HTTPException(status_code=404, detail=f"Model {request.model} not found")
    
    model_info = app_state.available_models[request.model]
    if not model_info.available:
        raise HTTPException(status_code=503, detail=f"Model {request.model} is not available")
    
    try:
        if model_info.type == "local":
            response = await test_ollama_model(request)
        else:
            response = await test_openrouter_model(request)
        
        return {
            "model": request.model,
            "prompt": request.prompt,
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "type": model_info.type
        }
    except Exception as e:
        logger.error(f"Error testing model {request.model}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def test_ollama_model(request: TestRequest) -> str:
    """Test an Ollama model"""
    model_config = Config.LOCAL_MODELS[request.model]
    
    payload = {
        "model": model_config["model"],
        "prompt": request.prompt,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 1000
        }
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{Config.OLLAMA_URL}/api/generate",
            json=payload
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Ollama API error")
        
        result = response.json()
        return result.get("response", "")

async def test_openrouter_model(request: TestRequest) -> str:
    """Test an OpenRouter model"""
    model_config = Config.CLOUD_MODELS[request.model]
    
    headers = {
        "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Companion AI Testing"
    }
    
    payload = {
        "model": model_config["model"],
        "messages": [
            {"role": "user", "content": request.prompt}
        ],
        "stream": False,
        "temperature": 0.7,
        "max_tokens": 1000
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{Config.OPENROUTER_URL}/chat/completions",
            headers=headers,
            json=payload
        )
        
        if response.status_code != 200:
            error_detail = f"OpenRouter API error: {response.status_code}"
            try:
                error_data = response.json()
                error_detail += f" - {error_data.get('error', {}).get('message', '')}"
            except:
                pass
            raise HTTPException(status_code=response.status_code, detail=error_detail)
        
        result = response.json()
        return result["choices"][0]["message"]["content"]

@app.post("/api/chat")
async def chat_completion(request: ChatRequest):
    """Chat completion endpoint with streaming support"""
    if request.model not in app_state.available_models:
        raise HTTPException(status_code=404, detail=f"Model {request.model} not found")
    
    model_info = app_state.available_models[request.model]
    if not model_info.available:
        raise HTTPException(status_code=503, detail=f"Model {request.model} is not available")
    
    if request.stream:
        if model_info.type == "local":
            return StreamingResponse(
                stream_ollama_chat(request),
                media_type="text/plain"
            )
        else:
            return StreamingResponse(
                stream_openrouter_chat(request),
                media_type="text/plain"
            )
    else:
        # Non-streaming response
        try:
            if model_info.type == "local":
                response = await complete_ollama_chat(request)
            else:
                response = await complete_openrouter_chat(request)
            
            return response
        except Exception as e:
            logger.error(f"Error in chat completion: {e}")
            raise HTTPException(status_code=500, detail=str(e))

async def stream_ollama_chat(request: ChatRequest) -> AsyncGenerator[str, None]:
    """Stream chat completion from Ollama"""
    model_config = Config.LOCAL_MODELS[request.model]
    
    # Convert messages to prompt
    prompt = "\n".join([f"{msg.role}: {msg.content}" for msg in request.messages])
    
    payload = {
        "model": model_config["model"],
        "prompt": prompt,
        "stream": True,
        "options": {
            "temperature": request.temperature,
            "num_predict": request.max_tokens or 1000
        }
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{Config.OLLAMA_URL}/api/generate",
            json=payload
        ) as response:
            async for line in response.aiter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        if "response" in data:
                            yield f"data: {json.dumps({'content': data['response']})}\n\n"
                        if data.get("done", False):
                            yield f"data: {json.dumps({'done': True})}\n\n"
                            break
                    except json.JSONDecodeError:
                        continue

async def stream_openrouter_chat(request: ChatRequest) -> AsyncGenerator[str, None]:
    """Stream chat completion from OpenRouter"""
    model_config = Config.CLOUD_MODELS[request.model]
    
    headers = {
        "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Companion AI Chat"
    }
    
    payload = {
        "model": model_config["model"],
        "messages": [{"role": msg.role, "content": msg.content} for msg in request.messages],
        "stream": True,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens or 1000
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{Config.OPENROUTER_URL}/chat/completions",
            headers=headers,
            json=payload
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]  # Remove "data: " prefix
                    if data_str.strip() == "[DONE]":
                        yield f"data: {json.dumps({'done': True})}\n\n"
                        break
                    try:
                        data = json.loads(data_str)
                        if "choices" in data and data["choices"]:
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield f"data: {json.dumps({'content': delta['content']})}\n\n"
                    except json.JSONDecodeError:
                        continue

async def complete_ollama_chat(request: ChatRequest) -> ChatResponse:
    """Complete chat with Ollama (non-streaming)"""
    # Implementation for non-streaming Ollama chat
    # This is a simplified version - you can expand as needed
    raise HTTPException(status_code=501, detail="Non-streaming Ollama chat not implemented yet")

async def complete_openrouter_chat(request: ChatRequest) -> ChatResponse:
    """Complete chat with OpenRouter (non-streaming)"""
    # Implementation for non-streaming OpenRouter chat
    # This is a simplified version - you can expand as needed
    raise HTTPException(status_code=501, detail="Non-streaming OpenRouter chat not implemented yet")

@app.get("/api/status")
async def get_status():
    """Get detailed system status"""
    await check_ollama_status()
    await check_openrouter_status()
    
    return {
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "ollama": {
                "available": app_state.ollama_available,
                "url": Config.OLLAMA_URL
            },
            "openrouter": {
                "available": app_state.openrouter_available,
                "configured": bool(Config.OPENROUTER_API_KEY)
            }
        },
        "models": {
            "local": len([m for m in app_state.available_models.values() if m.type == "local"]),
            "cloud": len([m for m in app_state.available_models.values() if m.type == "cloud"]),
            "total": len(app_state.available_models)
        }
    }

# Main entry point
if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"🚀 Starting Companion Backend API on {Config.HOST}:{Config.PORT}")
    logger.info(f"📖 API Documentation: http://{Config.HOST}:{Config.PORT}/docs")
    
    uvicorn.run(
        "backend_server:app",
        host=Config.HOST,
        port=Config.PORT,
        reload=True,
        log_level="info",
        access_log=True
    )
