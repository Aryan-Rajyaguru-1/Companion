#!/usr/bin/env python3
"""
Revoke Manager
==============

Handles rollback of autonomous changes
"""

import logging
import subprocess
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class RevokeManager:
    """Manage change revocation"""
    
    def __init__(self, project_root):
        self.project_root = project_root
        logger.info("🔙 Revoke Manager initialized")
    
    def revoke_last_change(self) -> bool:
        """Revoke the last autonomous change"""
        try:
            # Get last auto commit
            result = subprocess.run(
                ['git', 'log', '--grep=🤖 AUTO:', '--format=%H', '-n', '1'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True
            )
            
            commit_hash = result.stdout.strip()
            if not commit_hash:
                logger.warning("⚠️  No autonomous commits found")
                return False
            
            return self.revoke_change(commit_hash)
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Revoke failed: {e}")
            return False
    
    def revoke_change(self, commit_hash: str) -> bool:
        """Revoke specific commit"""
        try:
            subprocess.run(
                ['git', 'revert', '--no-edit', commit_hash],
                cwd=self.project_root,
                check=True
            )
            logger.info(f"✅ Revoked commit: {commit_hash[:8]}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Revert failed: {e}")
            return False
    
    def get_change_history(self) -> List[Dict[str, Any]]:
        """Get history of autonomous changes"""
        try:
            result = subprocess.run(
                ['git', 'log', '--grep=🤖 AUTO:', '--format=%H|%s|%ai', '-n', '50'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True
            )
            
            history = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                hash_part, msg, date = line.split('|', 2)
                history.append({
                    'commit': hash_part,
                    'message': msg,
                    'date': date
                })
            
            return history
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ History fetch failed: {e}")
            return []
