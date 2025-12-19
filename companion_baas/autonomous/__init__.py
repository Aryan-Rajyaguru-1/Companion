"""
Autonomous Self-Modification System
====================================

Unrestricted autonomous intelligence with:
- Full filesystem access
- Self-modification capabilities
- Continuous evolution
- Zero restrictions
- Daemon mode for 24/7 operation
"""

from .file_controller import UnrestrictedFileController
from .self_modifier import UnrestrictedSelfModifier
from .code_analyzer import CodeAnalyzer
from .code_generator import CodeGenerator
from .git_manager import GitManager
from .summary_generator import SummaryGenerator
from .revoke_manager import RevokeManager
from .autonomous_daemon import AutonomousDaemon
from .config import AutonomousConfig

__all__ = [
    'UnrestrictedFileController',
    'UnrestrictedSelfModifier',
    'CodeAnalyzer',
    'CodeGenerator',
    'GitManager',
    'SummaryGenerator',
    'RevokeManager',
    'AutonomousDaemon',
    'AutonomousConfig',
]
