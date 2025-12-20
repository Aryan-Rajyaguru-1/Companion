#!/usr/bin/env python3
"""
Chat Controller - Unified Chat Management System
===============================================

Handles all chat operations with proper conversation management,
agent routing, and message schema enforcement.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid
import logging
# Import database
try:
    from ..core.database import db
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from companion_baas.core.database import db

logger = logging.getLogger(__name__)

class Message:
    """Standardized message schema"""
    def __init__(self, role: str, content: str, message_type: str = "text",
                 agent: Optional[str] = None, metadata: Optional[Dict] = None):
        self.id = str(uuid.uuid4())
        self.role = role  # user, assistant, system, error
        self.type = message_type  # text, image, audio, etc.
        self.content = content
        self.agent = agent
        self.timestamp = datetime.utcnow().isoformat()
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "type": self.type,
            "content": self.content,
            "agent": self.agent,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }

class Conversation:
    """Conversation management"""
    def __init__(self, conversation_id: str):
        self.id = conversation_id
        self.messages: List[Message] = []
        self.created_at = datetime.utcnow().isoformat()
        self.updated_at = self.created_at
        self.metadata: Dict[str, Any] = {}

    def add_message(self, message: Message):
        self.messages.append(message)
        self.updated_at = datetime.utcnow().isoformat()

    def get_messages(self, limit: Optional[int] = None) -> List[Dict]:
        messages = [msg.to_dict() for msg in self.messages]
        if limit:
            messages = messages[-limit:]
        return messages

class ChatController:
    """Unified chat controller with agent routing"""

    def __init__(self):
        self.conversations: Dict[str, Conversation] = {}
        self.agents = {
            "companion": self._get_companion_agent(),
            "groq": self._get_groq_agent(),
            "minimal": self._get_minimal_agent()
        }

    def _get_companion_agent(self):
        """Get companion brain agent"""
        try:
            from ..core.brain import Brain
            brain = Brain()
            return lambda msg, **kwargs: brain.think(msg, **kwargs)
        except ImportError:
            # Fallback for direct execution
            try:
                import sys
                import os
                sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
                from companion_baas.core.brain import Brain
                brain = Brain()
                return lambda msg, **kwargs: brain.think(msg, **kwargs)
            except ImportError:
                logger.warning("Companion brain not available, using fallback")
                return self._get_minimal_agent()

    def _get_groq_agent(self):
        """Get Groq agent"""
        try:
            from groq import Groq
            import os
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEY not set")

            client = Groq(api_key=api_key)

            def groq_agent(message: str, **kwargs):
                response = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "You are Companion Brain, an intelligent AI assistant."},
                        {"role": "user", "content": message}
                    ],
                    model="llama-3.3-70b-versatile",
                    max_tokens=kwargs.get('max_tokens', 2048),
                    temperature=kwargs.get('temperature', 0.7)
                )
                return response.choices[0].message.content

            return groq_agent
        except Exception as e:
            logger.error(f"Failed to initialize Groq agent: {e}")
            return self._get_minimal_agent()

    def _get_minimal_agent(self):
        """Minimal fallback agent"""
        def minimal_agent(message: str, **kwargs):
            return f"Hello! I received: '{message}'. Configure a proper agent for full functionality."
        return minimal_agent

    def create_conversation(self, conversation_id: Optional[str] = None) -> str:
        """Create a new conversation"""
        if not conversation_id:
            conversation_id = f"conv_{int(datetime.utcnow().timestamp())}"

        conversation = Conversation(conversation_id)
        self.conversations[conversation_id] = conversation

        # Also store in database
        db.create_conversation(conversation_id)

        logger.info(f"Created conversation: {conversation_id}")
        return conversation_id

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get conversation by ID"""
        # Try memory first
        if conversation_id in self.conversations:
            return self.conversations[conversation_id]

        # Try database
        db_conv = db.get_conversation(conversation_id)
        if db_conv:
            conversation = Conversation(conversation_id)
            conversation.created_at = db_conv.get("created_at", conversation.created_at)
            conversation.updated_at = db_conv.get("updated_at", conversation.updated_at)
            conversation.metadata = db_conv.get("metadata", {})

            # Load messages
            for msg_data in db_conv.get("messages", []):
                msg = Message(
                    role=msg_data.get("role", "unknown"),
                    content=msg_data.get("content", ""),
                    message_type=msg_data.get("type", "text"),
                    agent=msg_data.get("agent"),
                    metadata=msg_data.get("metadata", {})
                )
                msg.id = msg_data.get("id", msg.id)
                msg.timestamp = msg_data.get("timestamp", msg.timestamp)
                conversation.messages.append(msg)

            self.conversations[conversation_id] = conversation
            return conversation

        return None

    def send_message(self, conversation_id: str, message: str,
                    agent: str = "companion", **kwargs) -> Message:
        """Send a message and get response"""

        # Get or create conversation
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            conversation = Conversation(conversation_id)
            self.conversations[conversation_id] = conversation
            db.create_conversation(conversation_id)

        # Add user message
        user_message = Message("user", message, "text")
        conversation.add_message(user_message)
        db.add_message(conversation_id, user_message.to_dict())

        # Get agent
        agent_func = self.agents.get(agent, self.agents["minimal"])

        # Generate response
        try:
            response_content = agent_func(message, **kwargs)
            response_message = Message("assistant", response_content, "text", agent=agent)
        except Exception as e:
            logger.error(f"Agent error: {e}")
            response_message = Message("system", f"Error: {str(e)}", "error", agent=agent)

        # Add response message
        conversation.add_message(response_message)
        db.add_message(conversation_id, response_message.to_dict())

        return response_message

    def get_conversation_history(self, conversation_id: str,
                               limit: Optional[int] = None) -> List[Dict]:
        """Get conversation message history"""
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return []

        return conversation.get_messages(limit)

    def list_conversations(self) -> List[Dict]:
        """List all conversations"""
        conversations = db.get_all_conversations()
        return [
            {
                "id": conv["id"],
                "message_count": conv["message_count"],
                "created_at": conv["created_at"],
                "updated_at": conv["updated_at"]
            }
            for conv in conversations
        ]

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation"""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]

        return db.delete_conversation(conversation_id)

# Global chat controller instance
chat_controller = ChatController()
