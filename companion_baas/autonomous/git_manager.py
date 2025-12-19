#!/usr/bin/env python3
"""
Git Manager
===========

Manages git operations for autonomous changes
"""

import logging
import subprocess
from datetime import datetime

logger = logging.getLogger(__name__)


class GitManager:
    """Manage git operations"""
    
    def __init__(self, project_root, config):
        self.project_root = project_root
        self.config = config
        logger.info("📚 Git Manager initialized")
    
    def commit_changes(self, message: str, files: list = None) -> str:
        """Commit changes to git"""
        try:
            # Add files
            if files:
                for f in files:
                    subprocess.run(['git', 'add', f], cwd=self.project_root, check=True)
            else:
                subprocess.run(['git', 'add', '-A'], cwd=self.project_root, check=True)
            
            # Commit
            full_message = f"{self.config.commit_message_prefix} {message}"
            subprocess.run(['git', 'commit', '-m', full_message], cwd=self.project_root, check=True)
            
            # Get commit hash
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                                  cwd=self.project_root, 
                                  capture_output=True, 
                                  text=True, 
                                  check=True)
            commit_hash = result.stdout.strip()
            
            logger.info(f"✅ Committed: {commit_hash[:8]}")
            return commit_hash
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Git commit failed: {e}")
            return None
    
    def get_last_commit(self) -> str:
        """Get last commit hash"""
        try:
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                                  cwd=self.project_root, 
                                  capture_output=True, 
                                  text=True, 
                                  check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None
