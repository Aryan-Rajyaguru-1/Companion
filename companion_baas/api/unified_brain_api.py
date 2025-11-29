#!/usr/bin/env python3
"""
Unified Brain REST API
======================

FastAPI wrapper for the unified brain - makes ALL phases accessible via HTTP.

Endpoints:
- POST /api/v1/think           - Main thinking endpoint
- POST /api/v1/execute         - Code execution
- POST /api/v1/tool/call       - Call a tool
- GET  /api/v1/tools           - List available tools
- POST /api/v1/search          - Hybrid search
- POST /api/v1/knowledge       - Knowledge retrieval
- POST /api/v1/web/scrape      - Web scraping
- POST /api/v1/web/news        - Get news
- POST /api/v1/web/search      - Web search
- GET  /api/v1/stats           - Performance stats
- GET  /api/v1/health          - Health check
- GET  /api/v1/history/{user_id} - Conversation history
- DELETE /api/v1/history/{user_id} - Clear history

Usage:
    uvicorn api.unified_brain_api:app --reload --port 8000
"""

import sys
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from core.unified_brain import create_brain, UnifiedCompanionBrain

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Companion Unified Brain API",
    description="Complete AI Brain with all 5 phases integrated",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global brain instance
brain: Optional[UnifiedCompanionBrain] = None


# ============================================================================
# REQUEST MODELS
# ============================================================================

class ThinkRequest(BaseModel):
    message: str = Field(..., description="User's input message")
    user_id: Optional[str] = Field(None, description="User identifier")
    conversation_id: Optional[str] = Field(None, description="Conversation ID")
    use_knowledge: bool = Field(False, description="Use knowledge base (Phase 1)")
    use_search: bool = Field(False, description="Use hybrid search (Phase 2)")
    use_tools: bool = Field(False, description="Allow tool calling (Phase 4)")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class ExecuteCodeRequest(BaseModel):
    code: str = Field(..., description="Code to execute")
    language: Optional[str] = Field(None, description="Programming language (python/javascript)")
    timeout: int = Field(10, description="Execution timeout in seconds")


class ToolCallRequest(BaseModel):
    tool_name: str = Field(..., description="Name of the tool to call")
    args: List[Any] = Field(default_factory=list, description="Positional arguments")
    kwargs: Dict[str, Any] = Field(default_factory=dict, description="Keyword arguments")
    use_cache: bool = Field(True, description="Use caching")


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    limit: int = Field(10, description="Maximum number of results")
    index_name: str = Field("documents", description="Index name")


class KnowledgeRequest(BaseModel):
    query: str = Field(..., description="Knowledge query")
    limit: int = Field(5, description="Maximum number of results")
    index_name: str = Field("knowledge", description="Index name")


class WebScrapeRequest(BaseModel):
    url: str = Field(..., description="URL to scrape")


class NewsRequest(BaseModel):
    query: Optional[str] = Field(None, description="News query")
    category: Optional[str] = Field(None, description="News category")
    limit: int = Field(10, description="Maximum number of articles")


class WebSearchRequest(BaseModel):
    query: str = Field(..., description="Web search query")
    limit: int = Field(10, description="Maximum number of results")


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class ThinkResponse(BaseModel):
    success: bool
    response: str
    metadata: Dict[str, Any]
    error: Optional[str] = None


class ExecuteCodeResponse(BaseModel):
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    execution_time: float
    language: str


class ToolCallResponse(BaseModel):
    success: bool
    result: Any = None
    cached: bool = False
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    phases: Dict[str, bool]
    timestamp: str


class StatsResponse(BaseModel):
    total_requests: int
    successful_requests: int
    failed_requests: int
    phase_usage: Dict[str, int]
    session_id: str
    uptime_seconds: float
    cache: Optional[Dict[str, Any]] = None
    monitoring: Optional[Dict[str, Any]] = None


# ============================================================================
# STARTUP/SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize brain on startup"""
    global brain
    logger.info("🚀 Initializing Unified Companion Brain...")
    brain = create_brain(app_type="api")
    logger.info(f"✅ Brain initialized: {brain}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("🛑 Shutting down Unified Companion Brain...")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_brain() -> UnifiedCompanionBrain:
    """Get brain instance"""
    if brain is None:
        raise HTTPException(status_code=500, detail="Brain not initialized")
    return brain


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Companion Unified Brain API",
        "version": "1.0.0",
        "status": "operational",
        "phases": 5,
        "docs": "/docs"
    }


@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint
    
    Returns system health status including all phases availability.
    """
    b = get_brain()
    health = b.get_health()
    return health


@app.get("/api/v1/stats", response_model=StatsResponse)
async def get_stats():
    """
    Get performance statistics
    
    Returns comprehensive stats including request counts, phase usage,
    cache performance, and monitoring metrics.
    """
    b = get_brain()
    stats = b.get_performance_stats()
    return stats


@app.post("/api/v1/think", response_model=ThinkResponse)
async def think(request: ThinkRequest):
    """
    Main thinking endpoint
    
    Process natural language queries with optional knowledge, search, and tools.
    
    Example:
        {
            "message": "What is Python?",
            "use_knowledge": true,
            "use_search": false,
            "user_id": "user123"
        }
    """
    b = get_brain()
    
    result = b.think(
        message=request.message,
        context=request.context,
        user_id=request.user_id,
        conversation_id=request.conversation_id,
        use_knowledge=request.use_knowledge,
        use_search=request.use_search,
        use_tools=request.use_tools
    )
    
    return result


@app.post("/api/v1/execute", response_model=ExecuteCodeResponse)
async def execute_code(request: ExecuteCodeRequest):
    """
    Execute code in a sandbox (Phase 4)
    
    Supports Python and JavaScript execution with security validation.
    
    Example:
        {
            "code": "print('Hello World!')",
            "language": "python"
        }
    """
    b = get_brain()
    
    result = b.execute_code(
        code=request.code,
        language=request.language,
        timeout=request.timeout
    )
    
    return result


@app.post("/api/v1/tool/call", response_model=ToolCallResponse)
async def call_tool(request: ToolCallRequest):
    """
    Call a registered tool (Phase 4)
    
    Execute any of the 23 built-in tools with provided arguments.
    
    Example:
        {
            "tool_name": "add",
            "args": [42, 58],
            "kwargs": {},
            "use_cache": true
        }
    """
    b = get_brain()
    
    result = b.call_tool(
        request.tool_name,
        *request.args,
        use_cache=request.use_cache,
        **request.kwargs
    )
    
    return result


@app.get("/api/v1/tools")
async def list_tools():
    """
    List all available tools (Phase 4)
    
    Returns list of all 23 built-in tools.
    """
    b = get_brain()
    tools = b.list_tools()
    
    return {
        "success": True,
        "tools": tools,
        "count": len(tools)
    }


@app.get("/api/v1/tools/search")
async def search_tools(query: str = Query(..., description="Search query")):
    """
    Search for tools by name/description (Phase 4)
    
    Find tools matching the query string.
    """
    b = get_brain()
    matching_tools = b.search_tools(query)
    
    return {
        "success": True,
        "query": query,
        "tools": matching_tools,
        "count": len(matching_tools)
    }


@app.post("/api/v1/search")
async def hybrid_search(request: SearchRequest):
    """
    Hybrid search endpoint (Phase 2)
    
    Perform text + vector search across indexed documents.
    
    Example:
        {
            "query": "machine learning",
            "limit": 10,
            "index_name": "documents"
        }
    """
    b = get_brain()
    
    result = b.hybrid_search(
        query=request.query,
        limit=request.limit,
        index_name=request.index_name
    )
    
    return result


@app.post("/api/v1/knowledge")
async def retrieve_knowledge(request: KnowledgeRequest):
    """
    Knowledge retrieval endpoint (Phase 1)
    
    Retrieve relevant knowledge from knowledge base using RAG.
    
    Example:
        {
            "query": "explain neural networks",
            "limit": 5
        }
    """
    b = get_brain()
    
    result = b.retrieve_knowledge(
        query=request.query,
        limit=request.limit,
        index_name=request.index_name
    )
    
    return result


@app.post("/api/v1/web/scrape")
async def scrape_web(request: WebScrapeRequest):
    """
    Web scraping endpoint (Phase 3)
    
    Scrape content from any URL.
    
    Example:
        {
            "url": "https://python.org"
        }
    """
    b = get_brain()
    
    result = b.scrape_web(url=request.url)
    return result


@app.post("/api/v1/web/news")
async def get_news(request: NewsRequest):
    """
    News retrieval endpoint (Phase 3)
    
    Get latest news articles.
    
    Example:
        {
            "query": "artificial intelligence",
            "limit": 10
        }
    """
    b = get_brain()
    
    result = b.get_news(
        query=request.query,
        category=request.category,
        limit=request.limit
    )
    
    return result


@app.post("/api/v1/web/search")
async def search_web(request: WebSearchRequest):
    """
    Web search endpoint (Phase 3)
    
    Search the web using DuckDuckGo.
    
    Example:
        {
            "query": "Python tutorials",
            "limit": 10
        }
    """
    b = get_brain()
    
    result = b.search_web(
        query=request.query,
        limit=request.limit
    )
    
    return result


@app.get("/api/v1/history/{user_id}")
async def get_conversation_history(
    user_id: str = Path(..., description="User ID"),
    limit: Optional[int] = Query(None, description="Limit number of messages")
):
    """
    Get conversation history
    
    Retrieve conversation history for a specific user.
    """
    b = get_brain()
    
    history = b.get_conversation_history(
        user_id=user_id,
        limit=limit
    )
    
    return {
        "success": True,
        "user_id": user_id,
        "history": history,
        "count": len(history)
    }


@app.delete("/api/v1/history/{user_id}")
async def clear_conversation_history(
    user_id: str = Path(..., description="User ID")
):
    """
    Clear conversation history
    
    Delete all conversation history for a specific user.
    """
    b = get_brain()
    
    b.clear_conversation(user_id=user_id)
    
    return {
        "success": True,
        "user_id": user_id,
        "message": "Conversation history cleared"
    }


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle all exceptions"""
    logger.error(f"Unhandled exception: {exc}")
    return {
        "success": False,
        "error": str(exc),
        "type": type(exc).__name__
    }


if __name__ == "__main__":
    import uvicorn
    
    print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║                  Companion Unified Brain API Server                       ║
║                                                                           ║
║  All 5 phases accessible via REST API:                                   ║
║  • Phase 1: Knowledge retrieval                                          ║
║  • Phase 2: Hybrid search                                                ║
║  • Phase 3: Web intelligence                                             ║
║  • Phase 4: Code execution + tools                                       ║
║  • Phase 5: Optimization                                                 ║
║                                                                           ║
║  API Documentation: http://localhost:8000/docs                           ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
""")
    
    uvicorn.run(
        "unified_brain_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
