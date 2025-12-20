#!/usr/bin/env python3
"""
Chat Controller
===============

Central controller for chat operations, message routing, and conversation management.
Handles the business logic for chat interactions, agent selection, and response generation.
"""

from typing import Dict, List, Optional, Any
import logging
import time
import uuid
from datetime import datetime, timezone

try:
    from ..routers.agent_router import AgentRouter
    from ..core.database import db
    from ..schemas.message import MessageCreate, MessageResponse
    from ..schemas.conversation import ConversationResponse
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    grandparent_dir = os.path.dirname(parent_dir)
    sys.path.insert(0, grandparent_dir)

    from companion_baas.api.routers.agent_router import AgentRouter
    from companion_baas.core.database import db
    from companion_baas.api.schemas.message import MessageCreate, MessageResponse
    from companion_baas.api.schemas.conversation import ConversationResponse

logger = logging.getLogger(__name__)

class ChatController:
    """Central controller for all chat operations"""

    def __init__(self):
        self.agent_router = AgentRouter()
        logger.info("ChatController initialized")

    async def process_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Process a chat message and return response

        Args:
            message: The user's message
            conversation_id: Optional conversation ID
            user_id: Optional user ID for personalization
            stream: Whether to stream the response

        Returns:
            Dict containing response data
        """
        start_time = time.time()

        # Generate conversation ID if not provided
        if not conversation_id:
            conversation_id = f"conv_{int(time.time())}_{str(uuid.uuid4())[:8]}"

        # Ensure conversation exists
        conversation = db.get_conversation(conversation_id)
        if not conversation:
            db.create_conversation(conversation_id)
            logger.info(f"Created new conversation: {conversation_id}")

        # Create user message
        user_message = MessageCreate(
            role="user",
            content=message,
            type="user",
            conversation_id=conversation_id,
            user_id=user_id
        )

        # Add timestamp to message dict
        user_message_dict = user_message.dict()
        user_message_dict["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Save user message
        saved_user_msg = db.add_message(conversation_id, user_message_dict)
        logger.info(f"Saved user message in conversation {conversation_id}")

        try:
            # Route to appropriate agent
            agent_name, agent_response = await self.agent_router.route_message(
                message=message,
                conversation_id=conversation_id,
                user_id=user_id,
                context=self._get_conversation_context(conversation_id)
            )

            # Create AI response message
            ai_message = MessageCreate(
                role="assistant",
                content=agent_response.get("content", ""),
                type="assistant",
                conversation_id=conversation_id,
                agent=agent_name,
                metadata=agent_response.get("metadata", {}),
                processing_time=time.time() - start_time
            )

            # Add timestamp to AI message dict
            ai_message_dict = ai_message.dict()
            ai_message_dict["timestamp"] = datetime.now(timezone.utc).isoformat()

            # Save AI message
            saved_ai_msg = db.add_message(conversation_id, ai_message_dict)

            # Update conversation metadata
            self._update_conversation_metadata(conversation_id, agent_name)

            response_data = {
                "message": MessageResponse(**saved_ai_msg),
                "conversation_id": conversation_id,
                "agent_used": agent_name,
                "processing_time": ai_message.processing_time,
                "stream": stream
            }

            if stream:
                response_data["stream_generator"] = self._create_stream_generator(
                    agent_response, conversation_id, saved_ai_msg["id"]
                )

            return response_data

        except Exception as e:
            logger.error(f"Error processing message: {e}")

            # Create error message
            error_message = MessageCreate(
                role="system",
                content=f"I apologize, but I encountered an error: {str(e)}",
                type="error",
                conversation_id=conversation_id,
                metadata={"error": str(e)}
            )

            # Add timestamp to error message dict
            error_message_dict = error_message.dict()
            error_message_dict["timestamp"] = datetime.now(timezone.utc).isoformat()

            saved_error_msg = db.add_message(conversation_id, error_message_dict)

            return {
                "message": MessageResponse(**saved_error_msg),
                "conversation_id": conversation_id,
                "error": True,
                "processing_time": time.time() - start_time
            }

    def get_conversation(self, conversation_id: str) -> Optional[ConversationResponse]:
        """Get a conversation with all messages"""
        conversation = db.get_conversation(conversation_id)
        if not conversation:
            return None

        return ConversationResponse(
            conversation_id=conversation_id,
            messages=[MessageResponse(**msg) for msg in conversation["messages"]],
            created_at=conversation["created_at"],
            updated_at=conversation.get("updated_at", conversation["created_at"]),
            metadata=conversation.get("metadata", {})
        )

    def get_conversations(self, user_id: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Get list of conversations"""
        conversations = db.get_all_conversations()

        # Filter by user if provided
        if user_id:
            conversations = [c for c in conversations if c.get("user_id") == user_id]

        # Sort by updated_at desc
        conversations.sort(key=lambda x: x.get("updated_at", x["created_at"]), reverse=True)

        return conversations[:limit]

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation"""
        try:
            db.delete_conversation(conversation_id)
            logger.info(f"Deleted conversation: {conversation_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting conversation {conversation_id}: {e}")
            return False

    def _get_conversation_context(self, conversation_id: str) -> List[Dict]:
        """Get recent conversation context for agent routing"""
        conversation = db.get_conversation(conversation_id)
        if not conversation:
            return []

        messages = conversation.get("messages", [])
        # Return last 10 messages for context
        return messages[-10:] if len(messages) > 10 else messages

    def _update_conversation_metadata(self, conversation_id: str, agent_name: str):
        """Update conversation metadata with agent usage stats"""
        try:
            metadata = db.get_conversation_metadata(conversation_id) or {}

            # Track agent usage
            agent_usage = metadata.get("agent_usage", {})
            agent_usage[agent_name] = agent_usage.get(agent_name, 0) + 1
            metadata["agent_usage"] = agent_usage

            # Update last agent used
            metadata["last_agent"] = agent_name
            metadata["updated_at"] = datetime.now().isoformat()

            db.update_conversation_metadata(conversation_id, metadata)
        except Exception as e:
            logger.warning(f"Failed to update conversation metadata: {e}")

    def _create_stream_generator(self, agent_response: Dict, conversation_id: str, message_id: str):
        """Create a streaming response generator"""
        async def stream_generator():
            content = agent_response.get("content", "")
            words = content.split()

            current_content = ""
            for word in words:
                current_content += word + " "

                # Update the message in database with current content
                db.update_message_content(conversation_id, message_id, current_content)

                # Yield the current state
                yield {
                    "type": "chunk",
                    "content": current_content,
                    "message_id": message_id,
                    "conversation_id": conversation_id
                }

                # Small delay for streaming effect
                await asyncio.sleep(0.05)

            # Final update
            yield {
                "type": "done",
                "content": current_content,
                "message_id": message_id,
                "conversation_id": conversation_id
            }

        return stream_generator