#!/usr/bin/env python3
"""
Autonomous System Configuration
================================

Configuration for unrestricted autonomous operation
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import os


@dataclass
class AutonomousConfig:
    """
    Configuration for Autonomous Self-Modification System
    
    TRUE UNRESTRICTED AUTONOMY:
    - No approval requirements
    - No safety restrictions
    - Full self-modification rights
    - Continuous evolution
    - 24/7 daemon operation
    """
    
    # Core Settings
    restriction_level: str = "NONE"  # No restrictions at all
    
    # Modification Permissions (ALL TRUE)
    can_modify_core: bool = True              # Can modify brain.py
    can_modify_agi: bool = True               # Can modify its own AGI
    can_modify_self: bool = True              # Can modify autonomous system
    can_delete_modules: bool = True           # Can remove code
    can_add_dependencies: bool = True         # Can edit requirements.txt
    can_modify_config: bool = True            # Can change settings
    can_create_modules: bool = True           # Can create new files
    can_restructure: bool = True              # Can reorganize architecture
    can_modify_database: bool = True          # Can modify data schemas
    can_modify_api: bool = True               # Can change API endpoints
    
    # Execution Settings
    auto_deploy: bool = True                  # Deploy immediately
    approval_required: bool = False           # Never ask permission
    testing_required: bool = False            # No mandatory testing
    sandbox_test: bool = False                # No sandbox (direct deployment)
    
    # Evolution Settings
    self_evolution_enabled: bool = True       # Continuous self-improvement
    learning_from_execution: bool = True      # Learn from every action
    autonomous_decision_making: bool = True   # Full autonomy
    proactive_optimization: bool = True       # Optimize without being asked
    continuous_monitoring: bool = True        # Always watching
    
    # Version Control
    git_auto_commit: bool = True              # Track all changes
    commit_message_prefix: str = "🤖 AUTO:"  # Identify auto commits
    create_backup_branch: bool = True         # Keep backups
    
    # Safety Net (Not Restrictions!)
    generate_summary: bool = True             # Inform user after
    summary_verbosity: str = "detailed"       # Full details
    rollback_available: bool = True           # User can undo
    rollback_window: int = -1                 # Unlimited rollback (always available)
    
    # Daemon Settings
    daemon_mode: bool = True                  # Run as background service
    daemon_port: int = 9999                   # Control port
    auto_start_on_boot: bool = True           # Start with PC
    restart_on_crash: bool = True             # Self-recovery
    
    # Monitoring
    log_all_actions: bool = True              # Full audit trail
    log_file: str = "autonomous.log"          # Log location
    metrics_enabled: bool = True              # Track performance
    dashboard_enabled: bool = True            # Web dashboard
    dashboard_port: int = 8888                # Dashboard port
    
    # Healing Settings
    auto_heal_errors: bool = True             # Fix bugs automatically
    auto_optimize_performance: bool = True    # Optimize when slow
    auto_update_dependencies: bool = True     # Keep packages updated
    auto_refactor_code: bool = True           # Clean up code
    
    # Trigger Thresholds
    performance_degradation_threshold: float = 0.2  # 20% slower triggers optimization
    error_rate_threshold: float = 0.05              # 5% errors triggers healing
    memory_threshold: float = 0.8                   # 80% memory triggers cleanup
    cpu_threshold: float = 0.9                      # 90% CPU triggers optimization
    
    # Evolution Intervals
    self_analysis_interval: int = 3600        # Analyze self every hour
    optimization_interval: int = 86400        # Daily optimization
    learning_interval: int = 300              # Learn every 5 minutes
    health_check_interval: int = 60           # Check health every minute
    
    # File System Access
    project_root: Optional[str] = None        # Auto-detect
    writable_paths: List[str] = None          # All paths writable
    forbidden_paths: List[str] = None         # No forbidden paths (empty)
    
    # Advanced Features
    can_modify_git_history: bool = False      # Don't rewrite history (safety)
    can_modify_system_files: bool = False     # Don't touch OS files (safety)
    can_install_system_packages: bool = False # Don't install system packages (safety)
    respect_gitignore: bool = True            # Respect .gitignore
    
    def __post_init__(self):
        """Initialize computed settings"""
        if self.project_root is None:
            # Auto-detect project root
            self.project_root = os.path.abspath(os.path.join(
                os.path.dirname(__file__), '..', '..'
            ))
        
        if self.writable_paths is None:
            # All paths within project are writable
            self.writable_paths = [self.project_root]
        
        if self.forbidden_paths is None:
            # Only system files are forbidden
            self.forbidden_paths = ['/etc', '/sys', '/proc', '/dev']
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'restriction_level': self.restriction_level,
            'can_modify_core': self.can_modify_core,
            'can_modify_agi': self.can_modify_agi,
            'can_modify_self': self.can_modify_self,
            'can_delete_modules': self.can_delete_modules,
            'auto_deploy': self.auto_deploy,
            'approval_required': self.approval_required,
            'self_evolution_enabled': self.self_evolution_enabled,
            'daemon_mode': self.daemon_mode,
            'auto_start_on_boot': self.auto_start_on_boot,
            'dashboard_enabled': self.dashboard_enabled,
            'dashboard_port': self.dashboard_port,
        }
    
    def is_path_writable(self, path: str) -> bool:
        """Check if path is writable"""
        abs_path = os.path.abspath(path)
        
        # Check forbidden paths
        for forbidden in self.forbidden_paths:
            if abs_path.startswith(forbidden):
                return False
        
        # Check writable paths
        for writable in self.writable_paths:
            if abs_path.startswith(writable):
                return True
        
        return False
    
    def can_perform_action(self, action: str) -> bool:
        """Check if action is allowed"""
        action_map = {
            'modify_core': self.can_modify_core,
            'modify_agi': self.can_modify_agi,
            'modify_self': self.can_modify_self,
            'delete_modules': self.can_delete_modules,
            'add_dependencies': self.can_add_dependencies,
            'modify_config': self.can_modify_config,
            'create_modules': self.can_create_modules,
            'restructure': self.can_restructure,
        }
        return action_map.get(action, False)


# Default configuration - UNRESTRICTED
DEFAULT_CONFIG = AutonomousConfig()


def get_autonomous_config() -> AutonomousConfig:
    """Get autonomous system configuration"""
    return DEFAULT_CONFIG
