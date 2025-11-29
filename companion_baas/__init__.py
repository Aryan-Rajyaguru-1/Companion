"""
Companion BaaS (Brain as a Service)
====================================

A universal AI Brain framework that can power any application type.

Plug & Play AI for:
- Chatbots
- Code Assistants
- Image Generators
- Video Generators
- Research Tools
- And any AI-enabled application

Architecture:
    Brain (BaaS Framework) - Handles ALL AI logic
        ↓
    Apps (Chatbot, Coder, etc.) - Handle UI/UX only

By: Companion Team
Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "Companion Team"

from .core.brain import CompanionBrain
from .core.model_router import ModelRouter
from .core.context_manager import ContextManager
from .core.response_processor import ResponseProcessor
from .sdk.client import BrainClient, Brain

__all__ = [
    'CompanionBrain',
    'ModelRouter',
    'ContextManager',
    'ResponseProcessor',
    'BrainClient',
    'Brain'  # THE ONE-LINE AGI API!
]
