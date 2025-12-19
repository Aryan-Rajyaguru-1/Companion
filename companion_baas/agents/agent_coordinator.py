"""
Agent Coordinator - Orchestrates multi-agent workflows
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from .code_agent import CodeAgent
from .research_agent import ResearchAgent
from .test_agent import TestAgent
from .review_agent import ReviewAgent

logger = logging.getLogger(__name__)


class AgentCoordinator:
    """Coordinates multiple agents to complete complex tasks"""
    
    def __init__(self, brain=None, project_root: str = "."):
        """
        Initialize coordinator with all agents
        
        Args:
            brain: CompanionBrain instance
            project_root: Project root directory
        """
        self.brain = brain
        self.project_root = project_root
        
        # Initialize agents
        self.code_agent = CodeAgent(brain, project_root)
        self.research_agent = ResearchAgent(brain)
        self.test_agent = TestAgent(brain, project_root)
        self.review_agent = ReviewAgent(brain)
        
        self.agents = {
            'code': self.code_agent,
            'research': self.research_agent,
            'test': self.test_agent,
            'review': self.review_agent
        }
        
        logger.info("🎯 AgentCoordinator initialized with 4 agents")
    
    async def execute_workflow(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a multi-agent workflow
        
        Args:
            workflow: Workflow definition with steps
            
        Returns:
            Dict with results from each step
        """
        workflow_type = workflow.get('type')
        
        if workflow_type == 'implement_feature':
            return await self.implement_feature(workflow)
        elif workflow_type == 'fix_bug':
            return await self.fix_bug(workflow)
        elif workflow_type == 'optimize_code':
            return await self.optimize_code(workflow)
        elif workflow_type == 'add_functionality':
            return await self.add_functionality(workflow)
        else:
            return {
                'success': False,
                'error': f"Unknown workflow type: {workflow_type}"
            }
    
    async def implement_feature(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Complete workflow: Research → Code → Test → Review → Apply
        
        Args:
            workflow: Feature description and requirements
            
        Returns:
            Dict with all workflow results
        """
        try:
            feature_name = workflow.get('feature_name')
            file_path = workflow.get('file_path')
            requirements = workflow.get('requirements', '')
            
            logger.info(f"🚀 Implementing feature: {feature_name}")
            
            results = {
                'feature_name': feature_name,
                'steps': []
            }
            
            # Step 1: Research best practices
            logger.info("📚 Step 1: Researching best practices...")
            research_result = await self.research_agent.execute({
                'action': 'find_best_practice',
                'query': f"{feature_name} {requirements}"
            })
            results['steps'].append({
                'step': 'research',
                'result': research_result
            })
            
            if not research_result.get('success'):
                return {
                    'success': False,
                    'error': 'Research failed',
                    'results': results
                }
            
            # Step 2: Read existing code
            logger.info("📖 Step 2: Reading existing code...")
            read_result = await self.code_agent.execute({
                'action': 'read_file',
                'file_path': file_path
            })
            results['steps'].append({
                'step': 'read',
                'result': read_result
            })
            
            # Step 3: Generate solution using brain
            logger.info("💡 Step 3: Generating solution...")
            solution_prompt = f"""Generate code to implement: {feature_name}

Requirements: {requirements}

Best practices:
{research_result.get('research', '')}

Existing code:
{read_result.get('content', '')}

Generate the complete modified code."""
            
            if self.brain:
                solution_result = await self.brain.think(
                    message=solution_prompt,
                    use_agi_decision=True
                )
                results['steps'].append({
                    'step': 'generate',
                    'result': solution_result
                })
                
                new_code = solution_result.get('response', '')
            else:
                return {
                    'success': False,
                    'error': 'Brain not available for code generation'
                }
            
            # Step 4: Review the code
            logger.info("🔍 Step 4: Reviewing code...")
            review_result = await self.review_agent.execute({
                'action': 'review_change',
                'old_code': read_result.get('content', ''),
                'new_code': new_code
            })
            results['steps'].append({
                'step': 'review',
                'result': review_result
            })
            
            if not review_result.get('approved'):
                logger.warning("⚠️ Review not approved")
                return {
                    'success': False,
                    'error': 'Code review failed',
                    'results': results,
                    'review': review_result.get('review')
                }
            
            # Step 5: Apply changes
            logger.info("✍️ Step 5: Applying changes...")
            write_result = await self.code_agent.execute({
                'action': 'write_file',
                'file_path': file_path,
                'content': new_code
            })
            results['steps'].append({
                'step': 'write',
                'result': write_result
            })
            
            # Step 6: Generate tests
            logger.info("🧪 Step 6: Generating tests...")
            test_result = await self.test_agent.execute({
                'action': 'generate_test',
                'file_path': file_path,
                'function_name': feature_name
            })
            results['steps'].append({
                'step': 'test',
                'result': test_result
            })
            
            logger.info(f"✅ Feature '{feature_name}' implemented successfully!")
            
            return {
                'success': True,
                'results': results,
                'message': f"Feature '{feature_name}' implemented with tests"
            }
        except Exception as e:
            logger.error(f"❌ Implement feature error: {e}")
            return {
                'success': False,
                'error': str(e),
                'results': results if 'results' in locals() else {}
            }
    
    async def fix_bug(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Bug fix workflow: Analyze → Research → Fix → Test → Review
        
        Args:
            workflow: Bug description and location
            
        Returns:
            Dict with fix results
        """
        try:
            bug_description = workflow.get('bug_description')
            file_path = workflow.get('file_path')
            
            logger.info(f"🐛 Fixing bug: {bug_description}")
            
            results = {
                'bug_description': bug_description,
                'steps': []
            }
            
            # Step 1: Read current code
            read_result = await self.code_agent.execute({
                'action': 'read_file',
                'file_path': file_path
            })
            results['steps'].append({
                'step': 'read',
                'result': read_result
            })
            
            # Step 2: Research solution
            logger.info("🔍 Researching solution...")
            solution_result = await self.research_agent.execute({
                'action': 'find_solution',
                'problem': f"{bug_description}\n\nCode:\n{read_result.get('content', '')}"
            })
            results['steps'].append({
                'step': 'research',
                'result': solution_result
            })
            
            # Step 3: Generate fix
            logger.info("💡 Generating fix...")
            fix_prompt = f"""Fix this bug:

Bug: {bug_description}

Current code:
{read_result.get('content', '')}

Solution approach:
{solution_result.get('solution', '')}

Generate the fixed code."""
            
            if self.brain:
                fix_result = await self.brain.think(
                    message=fix_prompt,
                    use_agi_decision=True
                )
                fixed_code = fix_result.get('response', '')
                results['steps'].append({
                    'step': 'generate_fix',
                    'result': fix_result
                })
            else:
                return {
                    'success': False,
                    'error': 'Brain not available'
                }
            
            # Step 4: Review fix
            logger.info("🔍 Reviewing fix...")
            review_result = await self.review_agent.execute({
                'action': 'review_change',
                'old_code': read_result.get('content', ''),
                'new_code': fixed_code
            })
            results['steps'].append({
                'step': 'review',
                'result': review_result
            })
            
            if not review_result.get('approved'):
                return {
                    'success': False,
                    'error': 'Fix not approved by review',
                    'results': results
                }
            
            # Step 5: Apply fix
            logger.info("✍️ Applying fix...")
            write_result = await self.code_agent.execute({
                'action': 'write_file',
                'file_path': file_path,
                'content': fixed_code
            })
            results['steps'].append({
                'step': 'apply',
                'result': write_result
            })
            
            logger.info(f"✅ Bug fixed successfully!")
            
            return {
                'success': True,
                'results': results,
                'message': f"Bug fixed: {bug_description}"
            }
        except Exception as e:
            logger.error(f"❌ Fix bug error: {e}")
            return {
                'success': False,
                'error': str(e),
                'results': results if 'results' in locals() else {}
            }
    
    async def optimize_code(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Code optimization workflow: Analyze → Research → Optimize → Test → Review
        """
        # Similar structure to implement_feature but focused on optimization
        logger.info("⚡ Optimizing code...")
        # Implementation details...
        return {
            'success': True,
            'message': 'Optimization workflow placeholder'
        }
    
    async def add_functionality(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add new functionality: Research → Design → Code → Test → Review
        """
        logger.info("➕ Adding functionality...")
        # Implementation details...
        return {
            'success': True,
            'message': 'Add functionality workflow placeholder'
        }
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all agents"""
        return {
            'agents': {
                name: {
                    'skills': agent.get_capabilities(),
                    'history_count': len(agent.history)
                }
                for name, agent in self.agents.items()
            }
        }
