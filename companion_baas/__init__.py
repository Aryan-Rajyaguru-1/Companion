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

# Optional imports with fallbacks
try:
    from .core.brain import CompanionBrain
except ImportError:
    CompanionBrain = None

try:
    from .core.model_router import ModelRouter
except ImportError:
    ModelRouter = None

try:
    from .core.context_manager import ContextManager
except ImportError:
    ContextManager = None

try:
    from .core.response_processor import ResponseProcessor
except ImportError:
    ResponseProcessor = None

try:
    from .sdk.client import BrainClient, Brain
except ImportError:
    BrainClient = None
    Brain = None

__all__ = [
    'CompanionBrain',
    'ModelRouter',
    'ContextManager',
    'ResponseProcessor',
    'BrainClient',
    'Brain'  # THE ONE-LINE AGI API!
]
