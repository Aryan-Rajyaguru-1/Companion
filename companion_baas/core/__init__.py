"""
Companion BaaS Core Components
"""

# Optional imports with fallbacks
try:
    from .brain import CompanionBrain
except ImportError:
    CompanionBrain = None

try:
    from .model_router import ModelRouter
except ImportError:
    ModelRouter = None

try:
    from .context_manager import ContextManager
except ImportError:
    ContextManager = None

try:
    from .response_processor import ResponseProcessor
except ImportError:
    ResponseProcessor = None

__all__ = ['CompanionBrain', 'ModelRouter', 'ContextManager', 'ResponseProcessor']
