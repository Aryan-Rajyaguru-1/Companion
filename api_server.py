#!/usr/bin/env python3
"""
Companion Brain API Server - Cloud Deployment Ready
====================================================

FastAPI server exposing CompanionBrain AGI via REST API
Deploy to Railway, Render, Fly.io, or any cloud platform

Features:
- ✅ REST API for brain.think() with AGI
- ✅ Health check endpoints
- ✅ API key authentication
- ✅ Rate limiting
- ✅ CORS enabled
- ✅ Production-ready with uvicorn
- ✅ Environment-based configuration
"""

from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import os
import sys
import time
from datetime import datetime
import logging
import uvicorn
from collections import defaultdict

# Add companion_baas to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from companion_baas.sdk import BrainClient

# ============================================================================
# Configuration
# ============================================================================

# Environment variables
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
API_KEY = os.getenv("API_KEY", "your-secret-api-key-change-this")
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Initialize FastAPI App
# ============================================================================

app = FastAPI(
    title="Companion Brain API",
    description="AGI-powered intelligent assistant API with autonomous decision-making",
    version="2.0.0",
    docs_url="/docs" if ENVIRONMENT == "development" else None,
    redoc_url="/redoc" if ENVIRONMENT == "development" else None
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Initialize Companion Brain with AGI
# ============================================================================

try:
    companion_brain = BrainClient(
        app_type="api_service",
        enable_caching=True,
        enable_search=True,
        enable_learning=True,
        enable_agi=True,
        enable_autonomy=True  # Full AGI autonomy enabled
    )
    logger.info("🧠 Companion Brain initialized successfully with AGI!")
    
    # Log AGI status
    agi_status = companion_brain.get_agi_status()
    logger.info(f"🎭 AGI Enabled: {agi_status.get('agi_enabled')}")
    logger.info(f"🤖 Autonomy: {agi_status.get('autonomy_enabled')}")
    
except Exception as e:
    logger.error(f"❌ Failed to initialize Companion Brain: {e}")
    companion_brain = None

# ============================================================================
# Rate Limiting
# ============================================================================

class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)
    
    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed for client"""
        now = time.time()
        window_start = now - self.window_seconds
        
        # Clean old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if req_time > window_start
        ]
        
        # Check limit
        if len(self.requests[client_id]) >= self.max_requests:
            return False
        
        # Add current request
        self.requests[client_id].append(now)
        return True

rate_limiter = RateLimiter(max_requests=100, window_seconds=60)

# ============================================================================
# Request/Response Models
# ============================================================================

class ThinkRequest(BaseModel):
    """Request model for /think endpoint"""
    message: str = Field(..., description="User message/query to process")
    use_agi: bool = Field(True, description="Use AGI autonomous decision-making")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for history")

class ThinkResponse(BaseModel):
    """Response model for /think endpoint"""
    success: bool
    response: Optional[str] = None
    decision_details: Optional[Dict[str, Any]] = None
    thinking_time: Optional[float] = None
    error: Optional[str] = None
    timestamp: str

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    brain_status: str
    agi_enabled: bool
    autonomy_enabled: bool
    uptime: float
    timestamp: str

class StatsResponse(BaseModel):
    """Statistics response"""
    agi_stats: Dict[str, Any]
    learning_stats: Dict[str, Any]
    timestamp: str

# ============================================================================
# Authentication
# ============================================================================

async def verify_api_key(x_api_key: str = Header(None)):
    """Verify API key from header"""
    if ENVIRONMENT == "development":
        return True  # Skip in development
    
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True

# ============================================================================
# Helper Functions
# ============================================================================

startup_time = time.time()

def get_uptime() -> float:
    """Get server uptime in seconds"""
    return time.time() - startup_time

def get_client_id(request: Request) -> str:
    """Get client identifier for rate limiting"""
    # Use IP address or API key as identifier
    return request.client.host if request.client else "unknown"

# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint with API info"""
    return {
        "name": "Companion Brain API",
        "version": "2.0.0",
        "description": "AGI-powered intelligent assistant with autonomous decision-making",
        "endpoints": {
            "health": "/health",
            "think": "/api/think (POST)",
            "stats": "/api/stats",
            "agi_status": "/api/agi/status",
            "docs": "/docs" if ENVIRONMENT == "development" else "disabled"
        },
        "features": [
            "🧠 AGI Autonomous Decision-Making",
            "🔍 Web Search & Intelligence",
            "💾 Knowledge Management",
            "🎭 Personality & Reasoning",
            "📊 Learning & Optimization",
            "🔄 Multi-turn Conversations",
            "⚡ High Performance"
        ],
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    brain_status = "healthy" if companion_brain else "unavailable"
    
    agi_status = {}
    if companion_brain:
        try:
            agi_status = companion_brain.get_agi_status()
        except Exception as e:
            logger.error(f"Error getting AGI status: {e}")
            agi_status = {"agi_enabled": False, "autonomy_enabled": False}
    
    return HealthResponse(
        status="healthy",
        brain_status=brain_status,
        agi_enabled=agi_status.get("agi_enabled", False),
        autonomy_enabled=agi_status.get("autonomy_enabled", False),
        uptime=get_uptime(),
        timestamp=datetime.now().isoformat()
    )

@app.post("/api/think", response_model=ThinkResponse, dependencies=[Depends(verify_api_key)])
async def think(request: ThinkRequest, http_request: Request):
    """
    Main endpoint to interact with Companion Brain AGI
    
    The brain will autonomously:
    - Analyze the query type and intent
    - Decide which modules to use (from 30+ available)
    - Execute the optimal workflow
    - Learn from the interaction
    
    Example:
    ```
    POST /api/think
    {
        "message": "Explain quantum computing and find recent research papers",
        "use_agi": true,
        "context": {"user_level": "beginner"}
    }
    ```
    """
    if not companion_brain:
        raise HTTPException(status_code=503, detail="Brain service unavailable")
    
    # Rate limiting
    client_id = get_client_id(http_request)
    if not rate_limiter.is_allowed(client_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    start_time = time.time()
    
    try:
        logger.info(f"📥 Received think request: {request.message[:100]}")
        
        # Call brain with AGI
        result = companion_brain.think(
            message=request.message,
            use_agi_decision=request.use_agi
        )
        
        thinking_time = time.time() - start_time
        
        logger.info(f"✅ Thinking complete in {thinking_time:.2f}s")
        
        return ThinkResponse(
            success=True,
            response=result.get("response"),
            decision_details=result.get("decision_details"),
            thinking_time=thinking_time,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"❌ Error in think endpoint: {e}", exc_info=True)
        return ThinkResponse(
            success=False,
            error=str(e),
            timestamp=datetime.now().isoformat()
        )

@app.get("/api/agi/status")
async def agi_status(authenticated: bool = Depends(verify_api_key)):
    """Get AGI system status"""
    if not companion_brain:
        raise HTTPException(status_code=503, detail="Brain service unavailable")
    
    try:
        status = companion_brain.get_agi_status()
        return JSONResponse(content={
            "success": True,
            "status": status,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats", response_model=StatsResponse, dependencies=[Depends(verify_api_key)])
async def get_stats():
    """Get AGI decision and learning statistics"""
    if not companion_brain:
        raise HTTPException(status_code=503, detail="Brain service unavailable")
    
    try:
        agi_stats = companion_brain.get_agi_decision_stats()
        learning_stats = companion_brain.get_learning_stats()
        
        return StatsResponse(
            agi_stats=agi_stats,
            learning_stats=learning_stats,
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/conversation/start", dependencies=[Depends(verify_api_key)])
async def start_conversation():
    """Start a new conversation (returns conversation_id)"""
    conversation_id = f"conv_{int(time.time())}_{os.urandom(4).hex()}"
    return {
        "success": True,
        "conversation_id": conversation_id,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/modules")
async def list_modules(authenticated: bool = Depends(verify_api_key)):
    """List available brain modules"""
    modules = [
        "Knowledge Management", "Search", "Web Intelligence",
        "Code Execution", "Optimization", "Neural Reasoning",
        "Personality System", "Memory", "Learning Strategy",
        "AGI Decision Engine"
    ]
    
    return {
        "success": True,
        "modules": modules,
        "total": len(modules),
        "timestamp": datetime.now().isoformat()
    }

# ============================================================================
# Startup/Shutdown Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Run on server startup"""
    logger.info("=" * 60)
    logger.info("🚀 Companion Brain API Server Starting...")
    logger.info(f"🌍 Environment: {ENVIRONMENT}")
    logger.info(f"🔌 Port: {PORT}")
    logger.info(f"🧠 Brain Status: {'Ready' if companion_brain else 'Unavailable'}")
    
    if companion_brain:
        agi_status = companion_brain.get_agi_status()
        logger.info(f"🎭 AGI: {agi_status.get('agi_enabled')}")
        logger.info(f"🤖 Autonomy: {agi_status.get('autonomy_enabled')}")
    
    logger.info("=" * 60)

@app.on_event("shutdown")
async def shutdown_event():
    """Run on server shutdown"""
    logger.info("🛑 Companion Brain API Server Shutting Down...")

# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc) if ENVIRONMENT == "development" else None,
            "timestamp": datetime.now().isoformat()
        }
    )

# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    logger.info(f"Starting server on {HOST}:{PORT}")
    uvicorn.run(
        "api_server:app",
        host=HOST,
        port=PORT,
        reload=ENVIRONMENT == "development",
        log_level=LOG_LEVEL.lower()
    )
