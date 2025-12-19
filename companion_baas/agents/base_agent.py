"""
Base Agent class with common functionality
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all agents"""
    
    def __init__(self, name: str, brain=None):
        """
        Initialize agent
        
        Args:
            name: Agent name
            brain: Reference to CompanionBrain for LLM calls
        """
        self.name = name
        self.brain = brain
        self.history: List[Dict[str, Any]] = []
        self.skills: List[str] = []
        
        logger.info(f"🤖 Agent '{name}' initialized")
    
    @abstractmethod
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a task
        
        Args:
            task: Task description with parameters
            
        Returns:
            Dict with result, status, and metadata
        """
        pass
    
    def log_action(self, action: str, result: Any, metadata: Dict = None):
        """Log agent action for audit trail"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'agent': self.name,
            'action': action,
            'result': result,
            'metadata': metadata or {}
        }
        self.history.append(entry)
        logger.info(f"📝 {self.name}: {action}")
    
    async def think(self, prompt: str) -> str:
        """Use brain's LLM to think"""
        if not self.brain:
            return "No brain available for thinking"
        
        try:
            # Check if brain.think is async
            result = self.brain.think(
                message=f"[{self.name}] {prompt}",
                use_agi_decision=False
            )
            
            # Handle both sync and async
            if hasattr(result, '__await__'):
                result = await result
                
            if result.get('success'):
                return result.get('response', 'No response')
            return f"Error: {result.get('error')}"
        except Exception as e:
            logger.error(f"❌ {self.name} think error: {e}")
            return f"Error: {e}"
    
    def get_capabilities(self) -> List[str]:
        """Return list of agent capabilities"""
        return self.skills
    
    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent action history"""
        return self.history[-limit:]
