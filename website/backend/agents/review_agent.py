"""
Review Agent - Validates code changes before applying
"""

import logging
from typing import Dict, Any, List
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ReviewAgent(BaseAgent):
    """Agent specialized in code review"""
    
    def __init__(self, brain=None):
        super().__init__("ReviewAgent", brain)
        self.skills = [
            'review_code',
            'check_security',
            'verify_best_practices',
            'analyze_complexity'
        ]
        self.review_criteria = [
            'Code follows Python best practices',
            'Proper error handling present',
            'Type hints are used',
            'Docstrings are complete',
            'No security vulnerabilities',
            'Logging is appropriate',
            'Code is not overly complex'
        ]
    
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a review task"""
        action = task.get('action')
        
        if action == 'review_code':
            return await self.review_code(task.get('code'))
        elif action == 'review_change':
            return await self.review_change(
                task.get('old_code'),
                task.get('new_code')
            )
        else:
            return {
                'success': False,
                'error': f"Unknown action: {action}"
            }
    
    async def review_code(self, code: str) -> Dict[str, Any]:
        """Review code for quality and best practices"""
        try:
            if not self.brain:
                return {
                    'success': False,
                    'error': 'Brain not available for review'
                }
            
            prompt = f"""Review this code against these criteria:

{chr(10).join(f"- {c}" for c in self.review_criteria)}

Code:
{code}

Provide:
1. Overall assessment (APPROVE/REJECT/NEEDS_CHANGES)
2. Issues found (if any)
3. Suggestions for improvement
4. Security concerns (if any)"""
            
            response = await self.think(prompt)
            
            # Parse response to determine approval
            approved = 'APPROVE' in response and 'REJECT' not in response
            
            self.log_action('review_code', f"Review: {'APPROVED' if approved else 'NEEDS_WORK'}", {
                'code_length': len(code)
            })
            
            return {
                'success': True,
                'approved': approved,
                'review': response,
                'criteria': self.review_criteria
            }
        except Exception as e:
            logger.error(f"❌ Review error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def review_change(self, old_code: str, new_code: str) -> Dict[str, Any]:
        """Review code changes"""
        try:
            if not self.brain:
                return {
                    'success': False,
                    'error': 'Brain not available for review'
                }
            
            prompt = f"""Review this code change:

OLD CODE:
{old_code}

NEW CODE:
{new_code}

Analyze:
1. What changed and why?
2. Does it maintain or improve code quality?
3. Are there any regressions?
4. Is the change safe to apply?
5. Recommendation: APPROVE/REJECT/NEEDS_CHANGES"""
            
            response = await self.think(prompt)
            
            approved = 'APPROVE' in response and 'REJECT' not in response
            
            self.log_action('review_change', f"Change: {'APPROVED' if approved else 'NEEDS_WORK'}")
            
            return {
                'success': True,
                'approved': approved,
                'review': response
            }
        except Exception as e:
            logger.error(f"❌ Review change error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
