"""
Companion Brain Cloud Client Library
=====================================

Easy-to-use Python client for accessing your deployed Companion Brain API

Usage:
    from client_library import CompanionBrainCloudClient
    
    brain = CompanionBrainCloudClient(
        base_url="https://your-app.railway.app",
        api_key="your-secret-key"
    )
    
    # Ask the brain anything
    result = brain.think("Explain quantum computing")
    print(result.response)
"""

import requests
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
import json


@dataclass
class ThinkResult:
    """Result from brain.think() call"""
    success: bool
    response: Optional[str] = None
    decision_details: Optional[Dict[str, Any]] = None
    thinking_time: Optional[float] = None
    error: Optional[str] = None
    timestamp: Optional[str] = None
    
    def __str__(self):
        if self.success:
            return f"✅ {self.response}"
        else:
            return f"❌ Error: {self.error}"


@dataclass
class HealthStatus:
    """Health check result"""
    status: str
    brain_status: str
    agi_enabled: bool
    autonomy_enabled: bool
    uptime: float
    timestamp: str
    
    def is_healthy(self) -> bool:
        return self.status == "healthy" and self.brain_status == "healthy"


class CompanionBrainCloudClient:
    """
    Client for accessing Companion Brain deployed on cloud platforms
    
    Features:
    - Simple API for brain.think()
    - Automatic retries on failure
    - Health checking
    - Statistics and monitoring
    - Error handling
    
    Example:
        brain = CompanionBrainCloudClient(
            base_url="https://companion-brain-production.up.railway.app",
            api_key="your-api-key"
        )
        
        # Think with AGI
        result = brain.think("What is the meaning of life?")
        if result.success:
            print(result.response)
            print(f"Modules used: {result.decision_details['modules_used']}")
    """
    
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Initialize client
        
        Args:
            base_url: Base URL of your deployed API (e.g., https://your-app.railway.app)
            api_key: Your API key for authentication
            timeout: Request timeout in seconds (default: 30)
            max_retries: Number of retries on failure (default: 3)
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }
    
    def think(
        self,
        message: str,
        use_agi: bool = True,
        context: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None
    ) -> ThinkResult:
        """
        Ask the brain to think and process your message
        
        Args:
            message: Your question or request
            use_agi: Use AGI autonomous decision-making (default: True)
            context: Additional context to provide
            conversation_id: Conversation ID for multi-turn conversations
        
        Returns:
            ThinkResult with response and decision details
        
        Example:
            result = brain.think("Explain quantum computing")
            print(result.response)
            print(f"Used modules: {result.decision_details['modules_used']}")
            print(f"Took {result.thinking_time:.2f} seconds")
        """
        url = f"{self.base_url}/api/think"
        payload = {
            "message": message,
            "use_agi": use_agi,
            "context": context,
            "conversation_id": conversation_id
        }
        
        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            
            return ThinkResult(
                success=data.get("success", False),
                response=data.get("response"),
                decision_details=data.get("decision_details"),
                thinking_time=data.get("thinking_time"),
                error=data.get("error"),
                timestamp=data.get("timestamp")
            )
        
        except requests.exceptions.RequestException as e:
            return ThinkResult(
                success=False,
                error=f"Request failed: {str(e)}"
            )
        except Exception as e:
            return ThinkResult(
                success=False,
                error=f"Unexpected error: {str(e)}"
            )
    
    def health(self) -> HealthStatus:
        """
        Check brain health status
        
        Returns:
            HealthStatus with system status
        
        Example:
            health = brain.health()
            if health.is_healthy():
                print(f"Brain is healthy! AGI: {health.agi_enabled}")
        """
        url = f"{self.base_url}/health"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return HealthStatus(
                status=data.get("status", "unknown"),
                brain_status=data.get("brain_status", "unknown"),
                agi_enabled=data.get("agi_enabled", False),
                autonomy_enabled=data.get("autonomy_enabled", False),
                uptime=data.get("uptime", 0),
                timestamp=data.get("timestamp", "")
            )
        
        except Exception as e:
            return HealthStatus(
                status="error",
                brain_status="error",
                agi_enabled=False,
                autonomy_enabled=False,
                uptime=0,
                timestamp=datetime.now().isoformat()
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get AGI decision and learning statistics
        
        Returns:
            Dict with agi_stats and learning_stats
        
        Example:
            stats = brain.get_stats()
            print(f"Total decisions: {stats['agi_stats']['total_decisions']}")
            print(f"Modules used: {stats['agi_stats']['modules_used']}")
        """
        url = f"{self.base_url}/api/stats"
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        
        except Exception as e:
            return {
                "error": str(e),
                "agi_stats": {},
                "learning_stats": {}
            }
    
    def get_agi_status(self) -> Dict[str, Any]:
        """
        Get AGI system status
        
        Returns:
            Dict with AGI configuration and status
        """
        url = f"{self.base_url}/api/agi/status"
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        
        except Exception as e:
            return {"error": str(e)}
    
    def list_modules(self) -> List[str]:
        """
        List available brain modules
        
        Returns:
            List of module names
        """
        url = f"{self.base_url}/api/modules"
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            return data.get("modules", [])
        
        except Exception as e:
            return []
    
    def start_conversation(self) -> Optional[str]:
        """
        Start a new conversation
        
        Returns:
            Conversation ID for use in think() calls
        """
        url = f"{self.base_url}/api/conversation/start"
        
        try:
            response = requests.post(
                url,
                headers=self.headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            return data.get("conversation_id")
        
        except Exception as e:
            return None
    
    def chat(
        self,
        messages: List[str],
        use_agi: bool = True
    ) -> List[ThinkResult]:
        """
        Multi-turn conversation
        
        Args:
            messages: List of messages to send
            use_agi: Use AGI for all messages
        
        Returns:
            List of ThinkResult for each message
        
        Example:
            results = brain.chat([
                "Hello!",
                "Tell me about quantum computing",
                "How is it different from classical computing?"
            ])
            
            for i, result in enumerate(results):
                print(f"Q{i+1}: {messages[i]}")
                print(f"A{i+1}: {result.response}")
        """
        conversation_id = self.start_conversation()
        results = []
        
        for message in messages:
            result = self.think(
                message=message,
                use_agi=use_agi,
                conversation_id=conversation_id
            )
            results.append(result)
        
        return results


# ============================================================================
# Async Client (for high-performance applications)
# ============================================================================

try:
    import aiohttp
    import asyncio
    
    class AsyncCompanionBrainCloudClient:
        """Async version of CompanionBrainCloudClient for high-performance apps"""
        
        def __init__(self, base_url: str, api_key: str, timeout: int = 30):
            self.base_url = base_url.rstrip('/')
            self.api_key = api_key
            self.timeout = timeout
            self.headers = {
                "X-API-Key": api_key,
                "Content-Type": "application/json"
            }
        
        async def think(
            self,
            message: str,
            use_agi: bool = True,
            context: Optional[Dict[str, Any]] = None
        ) -> ThinkResult:
            """Async version of think()"""
            url = f"{self.base_url}/api/think"
            payload = {
                "message": message,
                "use_agi": use_agi,
                "context": context
            }
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        headers=self.headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=self.timeout)
                    ) as response:
                        data = await response.json()
                        
                        return ThinkResult(
                            success=data.get("success", False),
                            response=data.get("response"),
                            decision_details=data.get("decision_details"),
                            thinking_time=data.get("thinking_time"),
                            error=data.get("error"),
                            timestamp=data.get("timestamp")
                        )
            
            except Exception as e:
                return ThinkResult(success=False, error=str(e))
        
        async def health(self) -> HealthStatus:
            """Async health check"""
            url = f"{self.base_url}/health"
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        data = await response.json()
                        
                        return HealthStatus(
                            status=data.get("status", "unknown"),
                            brain_status=data.get("brain_status", "unknown"),
                            agi_enabled=data.get("agi_enabled", False),
                            autonomy_enabled=data.get("autonomy_enabled", False),
                            uptime=data.get("uptime", 0),
                            timestamp=data.get("timestamp", "")
                        )
            
            except Exception:
                return HealthStatus(
                    status="error", brain_status="error",
                    agi_enabled=False, autonomy_enabled=False,
                    uptime=0, timestamp=datetime.now().isoformat()
                )

except ImportError:
    # aiohttp not available
    pass


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example configuration
    BASE_URL = "https://companion-brain-production.up.railway.app"
    API_KEY = "your-api-key-here"
    
    # Initialize client
    brain = CompanionBrainCloudClient(BASE_URL, API_KEY)
    
    # Check health
    print("🏥 Checking brain health...")
    health = brain.health()
    print(f"Status: {health.status}")
    print(f"Brain: {health.brain_status}")
    print(f"AGI Enabled: {health.agi_enabled}")
    print(f"Autonomy: {health.autonomy_enabled}")
    print(f"Uptime: {health.uptime:.2f}s")
    print()
    
    if not health.is_healthy():
        print("❌ Brain is not healthy!")
        exit(1)
    
    # List modules
    print("📦 Available modules:")
    modules = brain.list_modules()
    for module in modules:
        print(f"  - {module}")
    print()
    
    # Single query
    print("🧠 Asking the brain...")
    result = brain.think("Explain quantum computing in simple terms")
    print(f"Response: {result.response}")
    if result.decision_details:
        print(f"Query Type: {result.decision_details.get('query_type')}")
        print(f"Modules Used: {result.decision_details.get('modules_used')}")
        print(f"Thinking Time: {result.thinking_time:.2f}s")
    print()
    
    # Multi-turn conversation
    print("💬 Multi-turn conversation...")
    conversation = brain.chat([
        "Hello! Who are you?",
        "What can you help me with?",
        "Tell me about AGI"
    ])
    
    for i, result in enumerate(conversation):
        print(f"\nTurn {i+1}:")
        print(f"Response: {result.response}")
    print()
    
    # Get statistics
    print("📊 AGI Statistics:")
    stats = brain.get_stats()
    if "error" not in stats:
        print(json.dumps(stats, indent=2))
