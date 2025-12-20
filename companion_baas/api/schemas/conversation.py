#!/usr/bin/env python3
"""
Conversation Schemas
====================

Pydantic models for conversation validation and serialization.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from .message import MessageResponse


class ConversationBase(BaseModel):
    """Base conversation schema"""
    title: Optional[str] = Field(None, description="Conversation title")


class ConversationCreate(ConversationBase):
    """Schema for creating new conversations"""
    user_id: Optional[str] = Field(None, description="User ID if authenticated")


class ConversationResponse(ConversationBase):
    """Schema for conversation responses"""
    conversation_id: str = Field(..., description="Unique conversation ID")
    messages: List[MessageResponse] = Field(default_factory=list, description="List of messages")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    user_id: Optional[str] = Field(None, description="User ID if authenticated")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class ConversationListItem(BaseModel):
    """Schema for conversation list items"""
    conversation_id: str = Field(..., description="Unique conversation ID")
    title: Optional[str] = Field(None, description="Conversation title")
    message_count: int = Field(..., description="Number of messages")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    last_agent: Optional[str] = Field(None, description="Last agent used")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")