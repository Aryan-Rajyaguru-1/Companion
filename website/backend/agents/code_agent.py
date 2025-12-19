"""
Code Agent - Handles reading, writing, and modifying code files
"""

import os
import ast
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class CodeAgent(BaseAgent):
    """Agent specialized in code operations"""
    
    def __init__(self, brain=None, project_root: str = "."):
        super().__init__("CodeAgent", brain)
        self.project_root = Path(project_root)
        self.skills = [
            'read_file',
            'write_file',
            'modify_function',
            'add_import',
            'refactor_code',
            'analyze_code_structure',
            'find_dependencies'
        ]
    
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a code-related task"""
        action = task.get('action')
        
        if action == 'read_file':
            return await self.read_file(task.get('file_path'))
        elif action == 'write_file':
            return await self.write_file(
                task.get('file_path'),
                task.get('content')
            )
        elif action == 'modify_function':
            return await self.modify_function(
                task.get('file_path'),
                task.get('function_name'),
                task.get('new_code')
            )
        elif action == 'analyze_structure':
            return await self.analyze_code_structure(task.get('file_path'))
        elif action == 'add_import':
            return await self.add_import(
                task.get('file_path'),
                task.get('import_statement')
            )
        else:
            return {
                'success': False,
                'error': f"Unknown action: {action}"
            }
    
    async def read_file(self, file_path: str) -> Dict[str, Any]:
        """Read a file's contents"""
        try:
            full_path = self.project_root / file_path
            if not full_path.exists():
                return {
                    'success': False,
                    'error': f"File not found: {file_path}"
                }
            
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.log_action('read_file', f"Read {len(content)} chars", {
                'file_path': file_path
            })
            
            return {
                'success': True,
                'content': content,
                'lines': len(content.split('\n')),
                'file_path': file_path
            }
        except Exception as e:
            logger.error(f"❌ Read file error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def write_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """Write content to a file"""
        try:
            full_path = self.project_root / file_path
            
            # Create directory if it doesn't exist
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Backup existing file
            if full_path.exists():
                backup_path = full_path.with_suffix(full_path.suffix + '.backup')
                full_path.rename(backup_path)
            
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.log_action('write_file', f"Wrote {len(content)} chars", {
                'file_path': file_path
            })
            
            return {
                'success': True,
                'file_path': file_path,
                'bytes_written': len(content.encode('utf-8'))
            }
        except Exception as e:
            logger.error(f"❌ Write file error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def modify_function(
        self,
        file_path: str,
        function_name: str,
        new_code: str
    ) -> Dict[str, Any]:
        """Modify a specific function in a file"""
        try:
            # Read current file
            read_result = await self.read_file(file_path)
            if not read_result.get('success'):
                return read_result
            
            content = read_result['content']
            
            # Parse Python AST to find function
            try:
                tree = ast.parse(content)
            except SyntaxError as e:
                return {
                    'success': False,
                    'error': f"Syntax error in file: {e}"
                }
            
            # Find function definition
            function_found = False
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == function_name:
                    function_found = True
                    # Get line numbers
                    start_line = node.lineno - 1
                    end_line = node.end_lineno
                    break
            
            if not function_found:
                return {
                    'success': False,
                    'error': f"Function '{function_name}' not found"
                }
            
            # Replace function
            lines = content.split('\n')
            indent = len(lines[start_line]) - len(lines[start_line].lstrip())
            new_lines = [' ' * indent + line for line in new_code.split('\n')]
            
            modified_content = '\n'.join(
                lines[:start_line] + new_lines + lines[end_line:]
            )
            
            # Write back
            write_result = await self.write_file(file_path, modified_content)
            
            if write_result.get('success'):
                self.log_action('modify_function', f"Modified {function_name}", {
                    'file_path': file_path,
                    'function_name': function_name
                })
            
            return write_result
        except Exception as e:
            logger.error(f"❌ Modify function error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def analyze_code_structure(self, file_path: str) -> Dict[str, Any]:
        """Analyze code structure (classes, functions, imports)"""
        try:
            read_result = await self.read_file(file_path)
            if not read_result.get('success'):
                return read_result
            
            content = read_result['content']
            
            try:
                tree = ast.parse(content)
            except SyntaxError as e:
                return {
                    'success': False,
                    'error': f"Syntax error: {e}"
                }
            
            structure = {
                'imports': [],
                'classes': [],
                'functions': [],
                'variables': []
            }
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        structure['imports'].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    for alias in node.names:
                        structure['imports'].append(f"{module}.{alias.name}")
                elif isinstance(node, ast.ClassDef):
                    structure['classes'].append({
                        'name': node.name,
                        'line': node.lineno,
                        'methods': [m.name for m in node.body if isinstance(m, ast.FunctionDef)]
                    })
                elif isinstance(node, ast.FunctionDef):
                    # Only top-level functions
                    if node.col_offset == 0:
                        structure['functions'].append({
                            'name': node.name,
                            'line': node.lineno,
                            'args': [arg.arg for arg in node.args.args]
                        })
            
            self.log_action('analyze_structure', f"Analyzed {file_path}", structure)
            
            return {
                'success': True,
                'structure': structure,
                'file_path': file_path
            }
        except Exception as e:
            logger.error(f"❌ Analyze structure error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def add_import(self, file_path: str, import_statement: str) -> Dict[str, Any]:
        """Add an import statement to a file"""
        try:
            read_result = await self.read_file(file_path)
            if not read_result.get('success'):
                return read_result
            
            content = read_result['content']
            lines = content.split('\n')
            
            # Find where to insert (after docstring/comments, before code)
            insert_line = 0
            in_docstring = False
            
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    in_docstring = not in_docstring
                elif not in_docstring and stripped and not stripped.startswith('#'):
                    insert_line = i
                    break
            
            # Check if import already exists
            if import_statement in content:
                return {
                    'success': True,
                    'message': 'Import already exists',
                    'file_path': file_path
                }
            
            # Insert import
            lines.insert(insert_line, import_statement)
            modified_content = '\n'.join(lines)
            
            write_result = await self.write_file(file_path, modified_content)
            
            if write_result.get('success'):
                self.log_action('add_import', f"Added: {import_statement}", {
                    'file_path': file_path
                })
            
            return write_result
        except Exception as e:
            logger.error(f"❌ Add import error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
