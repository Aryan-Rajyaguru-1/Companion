#!/usr/bin/env python3
"""
Message Schemas
================

Pydantic models for message validation and serialization.
Used across API endpoints and internal processing.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class MessageBase(BaseModel):
    """Base message schema"""
    role: str = Field(..., description="Message role: user, assistant, system, error")
    content: str = Field(..., description="Message content")
    type: str = Field(..., description="Message type: user, assistant, system, error")


class MessageCreate(MessageBase):
    """Schema for creating new messages"""
    conversation_id: str = Field(..., description="Conversation ID")
    user_id: Optional[str] = Field(None, description="User ID if authenticated")
    agent: Optional[str] = Field(None, description="Agent that generated this message")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")


class MessageResponse(MessageBase):
    """Schema for message responses"""
    id: str = Field(..., description="Unique message ID")
    conversation_id: str = Field(..., description="Conversation ID")
    user_id: Optional[str] = Field(None, description="User ID if authenticated")
    agent: Optional[str] = Field(None, description="Agent that generated this message")
    timestamp: str = Field(..., description="ISO timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class MessageUpdate(BaseModel):
    """Schema for updating messages (e.g., during streaming)"""
    content: Optional[str] = Field(None, description="Updated content")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata")


class StreamingMessage(BaseModel):
    """Schema for streaming message chunks"""
    type: str = Field(..., description="Chunk type: chunk, done, error")
    content: str = Field(..., description="Current content")
    message_id: str = Field(..., description="Message ID")
    conversation_id: str = Field(..., description="Conversation ID")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")