#!/usr/bin/env python3
"""
Agent Router
============

Routes messages to appropriate agents based on content analysis and context.
Implements intelligent agent selection and task distribution.
"""

import re
import logging
from typing import Dict, List, Optional, Any, Tuple
import asyncio

# Import agents using absolute paths for Vercel compatibility
try:
    from companion_baas.agents.code_agent import CodeAgent
    from companion_baas.agents.research_agent import ResearchAgent
    from companion_baas.agents.review_agent import ReviewAgent
    from companion_baas.agents.test_agent import TestAgent
    from companion_baas.core.brain import CompanionBrain
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.error(f"Failed to import agents: {e}")
    # Define dummy classes for Vercel deployment
    class CodeAgent:
        def __init__(self, brain): pass
        async def process(self, message, context=None): return {"content": "Code agent not available", "agent": "code"}
    
    class ResearchAgent:
        def __init__(self, brain): pass
        async def process(self, message, context=None): return {"content": "Research agent not available", "agent": "research"}
    
    class ReviewAgent:
        def __init__(self, brain): pass
        async def process(self, message, context=None): return {"content": "Review agent not available", "agent": "review"}
    
    class TestAgent:
        def __init__(self, brain): pass
        async def process(self, message, context=None): return {"content": "Test agent not available", "agent": "test"}
    
    class CompanionBrain:
        def __init__(self, app_type="vercel"): pass

class AgentRouter:
    """Routes messages to appropriate agents based on content and context"""

    def __init__(self):
        self.brain = CompanionBrain(app_type="agent_router")
        self.agents = {
            "code": CodeAgent(brain=self.brain),
            "research": ResearchAgent(brain=self.brain),
            "review": ReviewAgent(brain=self.brain),
            "test": TestAgent(brain=self.brain)
        }

        # Keywords for agent routing
        self.routing_keywords = {
            "code": [
                "code", "function", "class", "import", "file", "script", "programming",
                "python", "javascript", "java", "debug", "fix", "implement", "refactor",
                "git", "commit", "branch", "merge", "pull", "push"
            ],
            "research": [
                "research", "find", "search", "information", "data", "analyze",
                "study", "investigate", "explore", "discover", "learn", "documentation"
            ],
            "review": [
                "review", "check", "validate", "verify", "assess", "evaluate",
                "audit", "inspect", "examine", "analyze", "quality", "feedback"
            ],
            "test": [
                "test", "testing", "unit test", "integration", "qa", "quality assurance",
                "automated test", "test case", "coverage", "ci/cd", "pipeline"
            ]
        }

        logger.info("AgentRouter initialized with agents: " + ", ".join(self.agents.keys()))

    async def route_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        context: Optional[List[Dict]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Route a message to the most appropriate agent

        Args:
            message: The user's message
            conversation_id: Current conversation ID
            user_id: User ID for personalization
            context: Recent conversation context

        Returns:
            Tuple of (agent_name, response_dict)
        """
        try:
            # Analyze message to determine best agent
            agent_name = await self._analyze_message(message, context)

            # Get the agent
            agent = self.agents.get(agent_name)
            if not agent:
                logger.warning(f"Agent '{agent_name}' not found, falling back to brain")
                return await self._fallback_to_brain(message)

            # Create task for agent
            task = self._create_task(message, conversation_id, user_id, context)

            # Execute agent task
            logger.info(f"Routing message to agent: {agent_name}")
            result = await agent.execute(task)

            # Format response
            response = {
                "content": result.get("response", result.get("content", "Task completed")),
                "metadata": {
                    "agent": agent_name,
                    "task_type": task.get("action"),
                    "success": result.get("status") == "success",
                    "processing_details": result.get("metadata", {})
                }
            }

            return agent_name, response

        except Exception as e:
            logger.error(f"Error routing message: {e}")
            return await self._fallback_to_brain(message)

    async def _analyze_message(
        self,
        message: str,
        context: Optional[List[Dict]] = None
    ) -> str:
        """
        Analyze message content to determine best agent

        Uses keyword matching and context analysis
        """
        message_lower = message.lower()

        # Check for explicit agent mentions
        explicit_mentions = {
            "code": ["code agent", "coding", "programming task"],
            "research": ["research agent", "find information", "search for"],
            "review": ["review agent", "check code", "validate"],
            "test": ["test agent", "run tests", "testing"]
        }

        for agent_name, mentions in explicit_mentions.items():
            if any(mention in message_lower for mention in mentions):
                return agent_name

        # Keyword-based routing
        scores = {}
        for agent_name, keywords in self.routing_keywords.items():
            score = sum(1 for keyword in keywords if keyword in message_lower)
            scores[agent_name] = score

        # Get agent with highest score
        best_agent = max(scores, key=scores.get)

        # If no clear winner, use context or default to research
        if scores[best_agent] == 0:
            # Check conversation context for patterns
            if context:
                recent_agents = [msg.get("agent") for msg in context[-3:] if msg.get("agent")]
                if recent_agents:
                    # Continue with same agent if recent
                    return recent_agents[-1]

            # Default to research for general queries
            best_agent = "research"

        logger.info(f"Selected agent '{best_agent}' for message: {message[:50]}...")
        return best_agent

    def _create_task(
        self,
        message: str,
        conversation_id: Optional[str],
        user_id: Optional[str],
        context: Optional[List[Dict]]
    ) -> Dict[str, Any]:
        """Create a structured task for the agent"""
        return {
            "message": message,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "context": context or [],
            "timestamp": asyncio.get_event_loop().time(),
            "action": self._infer_action(message)
        }

    def _infer_action(self, message: str) -> str:
        """Infer the specific action from the message"""
        message_lower = message.lower()

        # Code actions
        if any(word in message_lower for word in ["read", "show", "display", "get file"]):
            return "read_file"
        elif any(word in message_lower for word in ["write", "create", "add file"]):
            return "write_file"
        elif any(word in message_lower for word in ["modify", "change", "update function"]):
            return "modify_function"
        elif any(word in message_lower for word in ["analyze", "structure", "dependencies"]):
            return "analyze_structure"

        # Research actions
        elif any(word in message_lower for word in ["search", "find", "lookup"]):
            return "search"
        elif any(word in message_lower for word in ["summarize", "explain"]):
            return "summarize"

        # Review actions
        elif any(word in message_lower for word in ["review", "check", "validate"]):
            return "review_code"

        # Test actions
        elif any(word in message_lower for word in ["test", "run tests"]):
            return "run_tests"

        # Default action
        return "process"

    async def _fallback_to_brain(self, message: str) -> Tuple[str, Dict[str, Any]]:
        """Fallback to brain when agent routing fails"""
        try:
            response = self.brain.think(message, use_agi=True)
            return "brain", {
                "content": response.get("response", "I apologize, but I couldn't process that request."),
                "metadata": {
                    "agent": "brain",
                    "fallback": True,
                    "reason": "agent_routing_failed"
                }
            }
        except Exception as e:
            logger.error(f"Brain fallback failed: {e}")
            return "system", {
                "content": "I apologize, but I'm experiencing technical difficulties. Please try again later.",
                "metadata": {
                    "agent": "system",
                    "error": True,
                    "reason": str(e)
                }
            }

    def get_available_agents(self) -> List[str]:
        """Get list of available agents"""
        return list(self.agents.keys())

    def get_agent_info(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific agent"""
        agent = self.agents.get(agent_name)
        if not agent:
            return None

        return {
            "name": agent.name,
            "skills": agent.skills,
            "description": self._get_agent_description(agent_name)
        }

    def _get_agent_description(self, agent_name: str) -> str:
        """Get human-readable description of agent"""
        descriptions = {
            "code": "Handles code reading, writing, modification, and analysis",
            "research": "Performs information search, analysis, and research tasks",
            "review": "Reviews code quality, validates implementations, and provides feedback",
            "test": "Manages testing, quality assurance, and CI/CD operations"
        }
        return descriptions.get(agent_name, "General purpose AI assistant")