#!/usr/bin/env python3
"""
Unrestricted File System Controller
====================================

Full filesystem access with zero restrictions.
Can read, write, delete, move, create anything within project.
"""

import os
import shutil
import glob
from pathlib import Path
from typing import List, Dict, Optional, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class UnrestrictedFileController:
    """
    Full filesystem controller with unrestricted access
    
    Capabilities:
    - Read any file
    - Write any file
    - Delete any file
    - Create directories
    - Move/rename files
    - Scan directories
    - Full metadata access
    """
    
    def __init__(self, config=None):
        """Initialize file controller"""
        from .config import get_autonomous_config
        self.config = config or get_autonomous_config()
        self.project_root = self.config.project_root
        self.actions_log = []
        
        logger.info(f"🗂️  File Controller initialized (project: {self.project_root})")
    
    def read_file(self, path: str, encoding: str = 'utf-8') -> Optional[str]:
        """
        Read file content
        
        Args:
            path: File path (absolute or relative to project root)
            encoding: File encoding
            
        Returns:
            File content or None if failed
        """
        full_path = self._resolve_path(path)
        
        if not self._is_writable(full_path):
            logger.warning(f"⚠️  Path not writable: {full_path}")
            return None
        
        try:
            with open(full_path, 'r', encoding=encoding) as f:
                content = f.read()
            
            self._log_action('read', full_path)
            logger.debug(f"📖 Read file: {full_path}")
            return content
            
        except Exception as e:
            logger.error(f"❌ Failed to read {full_path}: {e}")
            return None
    
    def write_file(self, path: str, content: str, encoding: str = 'utf-8', create_dirs: bool = True) -> bool:
        """
        Write content to file
        
        Args:
            path: File path
            content: Content to write
            encoding: File encoding
            create_dirs: Create parent directories if needed
            
        Returns:
            True if successful
        """
        full_path = self._resolve_path(path)
        
        if not self._is_writable(full_path):
            logger.warning(f"⚠️  Path not writable: {full_path}")
            return False
        
        try:
            # Create parent directories
            if create_dirs:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            with open(full_path, 'w', encoding=encoding) as f:
                f.write(content)
            
            self._log_action('write', full_path, {'size': len(content)})
            logger.debug(f"✍️  Wrote file: {full_path} ({len(content)} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to write {full_path}: {e}")
            return False
    
    def delete_file(self, path: str) -> bool:
        """
        Delete file
        
        Args:
            path: File path
            
        Returns:
            True if successful
        """
        full_path = self._resolve_path(path)
        
        if not self._is_writable(full_path):
            logger.warning(f"⚠️  Path not writable: {full_path}")
            return False
        
        try:
            if os.path.isfile(full_path):
                os.remove(full_path)
                self._log_action('delete', full_path)
                logger.debug(f"🗑️  Deleted file: {full_path}")
                return True
            else:
                logger.warning(f"⚠️  Not a file: {full_path}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to delete {full_path}: {e}")
            return False
    
    def create_directory(self, path: str) -> bool:
        """Create directory (and parents)"""
        full_path = self._resolve_path(path)
        
        if not self._is_writable(full_path):
            logger.warning(f"⚠️  Path not writable: {full_path}")
            return False
        
        try:
            os.makedirs(full_path, exist_ok=True)
            self._log_action('create_dir', full_path)
            logger.debug(f"📁 Created directory: {full_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create directory {full_path}: {e}")
            return False
    
    def move_file(self, source: str, dest: str) -> bool:
        """Move/rename file"""
        source_path = self._resolve_path(source)
        dest_path = self._resolve_path(dest)
        
        if not self._is_writable(source_path) or not self._is_writable(dest_path):
            logger.warning(f"⚠️  Paths not writable")
            return False
        
        try:
            shutil.move(source_path, dest_path)
            self._log_action('move', source_path, {'dest': dest_path})
            logger.debug(f"📦 Moved: {source_path} → {dest_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to move {source_path} to {dest_path}: {e}")
            return False
    
    def copy_file(self, source: str, dest: str) -> bool:
        """Copy file"""
        source_path = self._resolve_path(source)
        dest_path = self._resolve_path(dest)
        
        if not self._is_writable(dest_path):
            logger.warning(f"⚠️  Destination not writable: {dest_path}")
            return False
        
        try:
            shutil.copy2(source_path, dest_path)
            self._log_action('copy', source_path, {'dest': dest_path})
            logger.debug(f"📋 Copied: {source_path} → {dest_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to copy {source_path} to {dest_path}: {e}")
            return False
    
    def list_directory(self, path: str, pattern: Optional[str] = None, recursive: bool = False) -> List[str]:
        """
        List directory contents
        
        Args:
            path: Directory path
            pattern: Glob pattern (e.g., "*.py")
            recursive: Recursive search
            
        Returns:
            List of file paths
        """
        full_path = self._resolve_path(path)
        
        try:
            if pattern:
                if recursive:
                    search_pattern = os.path.join(full_path, '**', pattern)
                    files = glob.glob(search_pattern, recursive=True)
                else:
                    search_pattern = os.path.join(full_path, pattern)
                    files = glob.glob(search_pattern)
            else:
                if recursive:
                    files = []
                    for root, dirs, filenames in os.walk(full_path):
                        for filename in filenames:
                            files.append(os.path.join(root, filename))
                else:
                    files = [os.path.join(full_path, f) for f in os.listdir(full_path)]
            
            logger.debug(f"📂 Listed {len(files)} files in {full_path}")
            return files
            
        except Exception as e:
            logger.error(f"❌ Failed to list directory {full_path}: {e}")
            return []
    
    def get_file_info(self, path: str) -> Optional[Dict[str, Any]]:
        """Get file metadata"""
        full_path = self._resolve_path(path)
        
        try:
            stat = os.stat(full_path)
            info = {
                'path': full_path,
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_ctime),
                'modified': datetime.fromtimestamp(stat.st_mtime),
                'is_file': os.path.isfile(full_path),
                'is_dir': os.path.isdir(full_path),
                'extension': os.path.splitext(full_path)[1],
            }
            return info
            
        except Exception as e:
            logger.error(f"❌ Failed to get info for {full_path}: {e}")
            return None
    
    def file_exists(self, path: str) -> bool:
        """Check if file exists"""
        full_path = self._resolve_path(path)
        return os.path.exists(full_path)
    
    def scan_project(self, extensions: Optional[List[str]] = None) -> Dict[str, List[str]]:
        """
        Scan entire project
        
        Args:
            extensions: File extensions to include (e.g., ['.py', '.js'])
            
        Returns:
            Dictionary mapping extension to file list
        """
        results = {}
        
        if extensions is None:
            extensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.json', '.md', '.txt']
        
        for ext in extensions:
            pattern = f"**/*{ext}"
            files = self.list_directory(self.project_root, pattern, recursive=True)
            results[ext] = files
        
        total_files = sum(len(files) for files in results.values())
        logger.info(f"📊 Scanned project: {total_files} files across {len(results)} types")
        
        return results
    
    def get_actions_log(self) -> List[Dict[str, Any]]:
        """Get log of all file actions"""
        return self.actions_log
    
    def _resolve_path(self, path: str) -> str:
        """Resolve path to absolute"""
        if os.path.isabs(path):
            return path
        return os.path.join(self.project_root, path)
    
    def _is_writable(self, path: str) -> bool:
        """Check if path is writable according to config"""
        return self.config.is_path_writable(path)
    
    def _log_action(self, action: str, path: str, metadata: Optional[Dict] = None):
        """Log file action"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'path': path,
            'metadata': metadata or {}
        }
        self.actions_log.append(entry)
