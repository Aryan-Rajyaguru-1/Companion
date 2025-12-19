"""
Test Agent - Generates and runs tests for code
"""

import logging
import subprocess
from typing import Dict, Any, List
from pathlib import Path
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class TestAgent(BaseAgent):
    """Agent specialized in testing"""
    
    def __init__(self, brain=None, project_root: str = "."):
        super().__init__("TestAgent", brain)
        self.project_root = Path(project_root)
        self.skills = [
            'generate_test',
            'run_tests',
            'analyze_coverage',
            'create_test_file'
        ]
    
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a testing task"""
        action = task.get('action')
        
        if action == 'generate_test':
            return await self.generate_test(
                task.get('file_path'),
                task.get('function_name')
            )
        elif action == 'run_tests':
            return await self.run_tests(task.get('test_file'))
        else:
            return {
                'success': False,
                'error': f"Unknown action: {action}"
            }
    
    async def generate_test(
        self,
        file_path: str,
        function_name: str
    ) -> Dict[str, Any]:
        """Generate test for a function"""
        try:
            if not self.brain:
                return {
                    'success': False,
                    'error': 'Brain not available for test generation'
                }
            
            # Read the function code
            full_path = self.project_root / file_path
            with open(full_path, 'r') as f:
                content = f.read()
            
            prompt = f"""Generate a comprehensive pytest test for this function:

File: {file_path}
Function: {function_name}

Code:
{content}

Generate:
1. Test file content with proper imports
2. Multiple test cases (happy path, edge cases, errors)
3. Fixtures if needed
4. Assertions for all return values"""
            
            response = await self.think(prompt)
            
            self.log_action('generate_test', f"Generated test for {function_name}", {
                'file_path': file_path,
                'function_name': function_name
            })
            
            return {
                'success': True,
                'test_code': response,
                'function_name': function_name
            }
        except Exception as e:
            logger.error(f"❌ Generate test error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def run_tests(self, test_file: str = None) -> Dict[str, Any]:
        """Run pytest tests"""
        try:
            cmd = ['pytest', '-v']
            if test_file:
                cmd.append(str(self.project_root / test_file))
            else:
                cmd.append(str(self.project_root))
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            passed = 'failed' not in result.stdout.lower()
            
            self.log_action('run_tests', f"Tests {'passed' if passed else 'failed'}", {
                'test_file': test_file,
                'exit_code': result.returncode
            })
            
            return {
                'success': passed,
                'output': result.stdout,
                'errors': result.stderr,
                'exit_code': result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Tests timed out after 60s'
            }
        except Exception as e:
            logger.error(f"❌ Run tests error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
