"""
Multi-Agent System for Autonomous Code Modification
Each agent has specialized capabilities for different tasks
"""

from .code_agent import CodeAgent
from .research_agent import ResearchAgent
from .test_agent import TestAgent
from .review_agent import ReviewAgent
from .agent_coordinator import AgentCoordinator

__all__ = [
    'CodeAgent',
    'ResearchAgent',
    'TestAgent',
    'ReviewAgent',
    'AgentCoordinator'
]
