#!/usr/bin/env python3
"""
Agent Coordination System
=========================

Multi-agent orchestration and coordination:
- Specialized agent creation
- Task decomposition and delegation
- Inter-agent communication
- Consensus building
- Parallel and sequential execution
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import time

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Specialized agent roles"""
    ORCHESTRATOR = "orchestrator"      # Coordinates other agents
    RESEARCHER = "researcher"          # Information gathering
    ANALYZER = "analyzer"              # Data analysis
    PLANNER = "planner"               # Task planning
    EXECUTOR = "executor"             # Action execution
    CRITIC = "critic"                 # Quality assessment
    SPECIALIST = "specialist"         # Domain expert
    COMMUNICATOR = "communicator"     # User interaction


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class AgentMessage:
    """Message between agents"""
    sender: str
    receiver: str
    content: str
    message_type: str  # 'request', 'response', 'broadcast', 'query'
    metadata: Dict[str, Any]
    timestamp: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "content": self.content,
            "message_type": self.message_type,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }


@dataclass
class Task:
    """Single task to be executed"""
    id: str
    description: str
    assigned_to: Optional[str]
    status: TaskStatus
    priority: int  # 1-10, higher = more important
    dependencies: List[str]  # Task IDs that must complete first
    result: Optional[Any]
    metadata: Dict[str, Any]
    created_at: float
    completed_at: Optional[float]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "assigned_to": self.assigned_to,
            "status": self.status.value,
            "priority": self.priority,
            "dependencies": self.dependencies,
            "result": self.result,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "completed_at": self.completed_at
        }


@dataclass(order=True)
class Agent:
    """Individual agent in the system"""
    # All fields with proper ordering
    performance_score: float = field(default=1.0)  # Used for comparison/ordering
    id: str = field(default="", compare=False)
    name: str = field(default="", compare=False)
    role: AgentRole = field(default=AgentRole.SPECIALIST, compare=False)
    capabilities: List[str] = field(default_factory=list, compare=False)
    llm_function: Callable = field(default=None, compare=False, repr=False)
    current_task: Optional[Task] = field(default=None, compare=False)
    completed_tasks: int = field(default=0, compare=False)
    metadata: Dict[str, Any] = field(default_factory=dict, compare=False)
    
    async def process(self, task: Task) -> Any:
        """
        Process a task
        
        Args:
            task: Task to process
            
        Returns:
            Task result
        """
        logger.info(f"Agent {self.name} processing task: {task.description}")
        
        # Build prompt based on role
        prompt = self._build_prompt(task)
        
        # Execute using LLM
        try:
            result = await self._execute_with_llm(prompt, task)
            self.completed_tasks += 1
            return result
        except Exception as e:
            logger.error(f"Agent {self.name} failed task: {e}")
            raise
    
    def _build_prompt(self, task: Task) -> str:
        """Build prompt based on agent role"""
        role_prompts = {
            AgentRole.RESEARCHER: f"Research and gather information about: {task.description}",
            AgentRole.ANALYZER: f"Analyze the following and provide insights: {task.description}",
            AgentRole.PLANNER: f"Create a detailed plan for: {task.description}",
            AgentRole.EXECUTOR: f"Execute the following task: {task.description}",
            AgentRole.CRITIC: f"Critically evaluate: {task.description}",
            AgentRole.SPECIALIST: f"Provide expert analysis on: {task.description}",
            AgentRole.COMMUNICATOR: f"Communicate clearly about: {task.description}"
        }
        
        base_prompt = role_prompts.get(self.role, f"Complete this task: {task.description}")
        
        # Add context from metadata
        if task.metadata:
            context = "\n".join([f"{k}: {v}" for k, v in task.metadata.items()])
            base_prompt += f"\n\nContext:\n{context}"
        
        return base_prompt
    
    async def _execute_with_llm(self, prompt: str, task: Task) -> Any:
        """Execute task using LLM"""
        if asyncio.iscoroutinefunction(self.llm_function):
            response = await self.llm_function(prompt)
        else:
            response = self.llm_function(prompt)
        
        return response


class MessageBus:
    """Central message bus for inter-agent communication"""
    
    def __init__(self):
        self.messages: List[AgentMessage] = []
        self.subscribers: Dict[str, List[Callable]] = {}
        
    def publish(self, message: AgentMessage):
        """Publish message to bus"""
        self.messages.append(message)
        
        # Notify subscribers
        if message.receiver in self.subscribers:
            for callback in self.subscribers[message.receiver]:
                try:
                    callback(message)
                except Exception as e:
                    logger.error(f"Subscriber callback error: {e}")
    
    def subscribe(self, agent_id: str, callback: Callable):
        """Subscribe to messages for agent"""
        if agent_id not in self.subscribers:
            self.subscribers[agent_id] = []
        self.subscribers[agent_id].append(callback)
    
    def get_messages(self, agent_id: str, limit: int = 10) -> List[AgentMessage]:
        """Get messages for specific agent"""
        agent_messages = [m for m in self.messages if m.receiver == agent_id or m.receiver == "all"]
        return agent_messages[-limit:]


class TaskDecomposer:
    """Decompose complex tasks into subtasks"""
    
    def __init__(self, llm_function: Callable):
        self.llm_function = llm_function
    
    async def decompose(self, task_description: str) -> List[str]:
        """
        Decompose task into subtasks
        
        Args:
            task_description: Description of complex task
            
        Returns:
            List of subtask descriptions
        """
        prompt = f"""
Decompose the following complex task into smaller, manageable subtasks.
List each subtask on a new line, numbered.

Task: {task_description}

Subtasks:
"""
        
        if asyncio.iscoroutinefunction(self.llm_function):
            response = await self.llm_function(prompt)
        else:
            response = self.llm_function(prompt)
        
        # Parse response into list
        subtasks = []
        for line in response.strip().split('\n'):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith('-')):
                # Remove numbering
                subtask = line.lstrip('0123456789.-) ').strip()
                if subtask:
                    subtasks.append(subtask)
        
        return subtasks if subtasks else [task_description]


class ConsensusBuilder:
    """Build consensus from multiple agent responses"""
    
    def __init__(self, llm_function: Callable):
        self.llm_function = llm_function
    
    async def build_consensus(
        self,
        question: str,
        responses: List[Tuple[str, str]]  # (agent_name, response)
    ) -> str:
        """
        Build consensus from multiple perspectives
        
        Args:
            question: Original question
            responses: List of (agent_name, response) tuples
            
        Returns:
            Consensus response
        """
        if len(responses) == 1:
            return responses[0][1]
        
        # Build consensus prompt
        responses_text = "\n\n".join([
            f"Agent {name}:\n{response}"
            for name, response in responses
        ])
        
        prompt = f"""
Multiple agents have provided their perspectives on the following question.
Synthesize these responses into a comprehensive consensus answer.

Question: {question}

Agent Responses:
{responses_text}

Consensus Answer:
"""
        
        if asyncio.iscoroutinefunction(self.llm_function):
            consensus = await self.llm_function(prompt)
        else:
            consensus = self.llm_function(prompt)
        
        return consensus


class AgentPool:
    """Pool of available agents"""
    
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        
    def add_agent(self, agent: Agent):
        """Add agent to pool"""
        self.agents[agent.id] = agent
        logger.info(f"Added agent: {agent.name} ({agent.role.value})")
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get specific agent"""
        return self.agents.get(agent_id)
    
    def get_agents_by_role(self, role: AgentRole) -> List[Agent]:
        """Get all agents with specific role"""
        return [a for a in self.agents.values() if a.role == role]
    
    def get_available_agents(self) -> List[Agent]:
        """Get agents not currently processing tasks"""
        return [a for a in self.agents.values() if a.current_task is None]
    
    def get_best_agent_for_task(self, task: Task) -> Optional[Agent]:
        """
        Find best agent for task based on capabilities and performance
        
        Args:
            task: Task to assign
            
        Returns:
            Best matching agent or None
        """
        available = self.get_available_agents()
        if not available:
            return None
        
        # Score agents based on performance and capability match
        scores = []
        for agent in available:
            score = agent.performance_score
            
            # Boost score if task metadata matches capabilities
            if task.metadata.get("required_capability") in agent.capabilities:
                score *= 1.5
            
            scores.append((score, agent))
        
        # Return highest scoring agent
        scores.sort(reverse=True)
        return scores[0][1] if scores else None


class TaskScheduler:
    """Schedule and manage task execution"""
    
    def __init__(self, agent_pool: AgentPool):
        self.agent_pool = agent_pool
        self.tasks: Dict[str, Task] = {}
        self.task_counter = 0
    
    def create_task(
        self,
        description: str,
        priority: int = 5,
        dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Task:
        """Create new task"""
        self.task_counter += 1
        task_id = f"task_{self.task_counter}_{int(time.time())}"
        
        task = Task(
            id=task_id,
            description=description,
            assigned_to=None,
            status=TaskStatus.PENDING,
            priority=priority,
            dependencies=dependencies or [],
            result=None,
            metadata=metadata or {},
            created_at=time.time(),
            completed_at=None
        )
        
        self.tasks[task_id] = task
        return task
    
    def can_execute(self, task: Task) -> bool:
        """Check if task dependencies are met"""
        for dep_id in task.dependencies:
            dep_task = self.tasks.get(dep_id)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                return False
        return True
    
    def get_ready_tasks(self) -> List[Task]:
        """Get tasks ready for execution"""
        ready = []
        for task in self.tasks.values():
            if task.status == TaskStatus.PENDING and self.can_execute(task):
                ready.append(task)
        
        # Sort by priority
        ready.sort(key=lambda t: t.priority, reverse=True)
        return ready
    
    async def execute_task(self, task: Task, agent: Agent) -> Any:
        """Execute task with agent"""
        task.status = TaskStatus.IN_PROGRESS
        task.assigned_to = agent.id
        agent.current_task = task
        
        try:
            result = await agent.process(task)
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = time.time()
            
            logger.info(f"Task completed: {task.id}")
            return result
        
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.result = str(e)
            logger.error(f"Task failed: {task.id} - {e}")
            raise
        
        finally:
            agent.current_task = None


class AgentCoordinationSystem:
    """
    Unified Agent Coordination System
    Orchestrates multiple specialized agents
    """
    
    def __init__(self, llm_function: Callable):
        self.llm_function = llm_function
        self.agent_pool = AgentPool()
        self.task_scheduler = TaskScheduler(self.agent_pool)
        self.message_bus = MessageBus()
        self.task_decomposer = TaskDecomposer(llm_function)
        self.consensus_builder = ConsensusBuilder(llm_function)
        
        self.enabled = True
        logger.info("✅ Agent Coordination System initialized")
    
    def create_agent(
        self,
        name: str,
        role: AgentRole,
        capabilities: Optional[List[str]] = None,
        llm_function: Optional[Callable] = None
    ) -> Agent:
        """
        Create and register new agent
        
        Args:
            name: Agent name
            role: Agent role
            capabilities: List of capabilities
            llm_function: Optional custom LLM function
            
        Returns:
            Created Agent
        """
        agent_id = f"agent_{name.lower().replace(' ', '_')}_{int(time.time())}"
        
        agent = Agent(
            id=agent_id,
            name=name,
            role=role,
            capabilities=capabilities or [],
            llm_function=llm_function or self.llm_function
        )
        
        self.agent_pool.add_agent(agent)
        return agent
    
    async def execute_task(
        self,
        description: str,
        decompose: bool = False,
        use_multiple_agents: bool = False,
        priority: int = 5
    ) -> Any:
        """
        Execute task with agent coordination
        
        Args:
            description: Task description
            decompose: Whether to decompose into subtasks
            use_multiple_agents: Use multiple agents for consensus
            priority: Task priority
            
        Returns:
            Task result
        """
        if decompose:
            # Decompose into subtasks
            subtasks = await self.task_decomposer.decompose(description)
            logger.info(f"Decomposed into {len(subtasks)} subtasks")
            
            # Create tasks for each subtask
            task_objects = []
            for subtask in subtasks:
                task = self.task_scheduler.create_task(
                    description=subtask,
                    priority=priority
                )
                task_objects.append(task)
            
            # Execute subtasks
            results = []
            for task in task_objects:
                agent = self.agent_pool.get_best_agent_for_task(task)
                if not agent:
                    logger.warning(f"No available agent for task: {task.id}")
                    continue
                
                result = await self.task_scheduler.execute_task(task, agent)
                results.append(result)
            
            # Combine results
            return "\n\n".join([str(r) for r in results])
        
        elif use_multiple_agents:
            # Get multiple agents for different perspectives
            available = self.agent_pool.get_available_agents()[:3]  # Max 3 agents
            
            if not available:
                raise RuntimeError("No available agents")
            
            # Execute with multiple agents
            responses = []
            for agent in available:
                task = self.task_scheduler.create_task(
                    description=description,
                    priority=priority
                )
                result = await self.task_scheduler.execute_task(task, agent)
                responses.append((agent.name, str(result)))
            
            # Build consensus
            consensus = await self.consensus_builder.build_consensus(
                description, responses
            )
            return consensus
        
        else:
            # Single agent execution
            task = self.task_scheduler.create_task(
                description=description,
                priority=priority
            )
            
            agent = self.agent_pool.get_best_agent_for_task(task)
            if not agent:
                raise RuntimeError("No available agents")
            
            result = await self.task_scheduler.execute_task(task, agent)
            return result
    
    async def parallel_execute(
        self,
        tasks: List[str],
        priority: int = 5
    ) -> List[Any]:
        """
        Execute multiple tasks in parallel
        
        Args:
            tasks: List of task descriptions
            priority: Task priority
            
        Returns:
            List of results
        """
        # Create task objects
        task_objects = [
            self.task_scheduler.create_task(desc, priority=priority)
            for desc in tasks
        ]
        
        # Execute in parallel
        coroutines = []
        for task in task_objects:
            agent = self.agent_pool.get_best_agent_for_task(task)
            if agent:
                coroutines.append(
                    self.task_scheduler.execute_task(task, agent)
                )
        
        results = await asyncio.gather(*coroutines, return_exceptions=True)
        return results
    
    def send_message(
        self,
        sender: str,
        receiver: str,
        content: str,
        message_type: str = "request"
    ):
        """
        Send message between agents
        
        Args:
            sender: Sender agent ID
            receiver: Receiver agent ID
            content: Message content
            message_type: Message type
        """
        message = AgentMessage(
            sender=sender,
            receiver=receiver,
            content=content,
            message_type=message_type,
            metadata={},
            timestamp=time.time()
        )
        self.message_bus.publish(message)
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all agents"""
        return {
            "total_agents": len(self.agent_pool.agents),
            "available_agents": len(self.agent_pool.get_available_agents()),
            "agents": [
                {
                    "name": agent.name,
                    "role": agent.role.value,
                    "completed_tasks": agent.completed_tasks,
                    "performance": agent.performance_score,
                    "busy": agent.current_task is not None
                }
                for agent in self.agent_pool.agents.values()
            ]
        }


# Convenience function
def create_coordination_system(llm_function: Callable) -> AgentCoordinationSystem:
    """
    Create agent coordination system
    
    Args:
        llm_function: LLM function for agents
        
    Returns:
        AgentCoordinationSystem instance
    """
    return AgentCoordinationSystem(llm_function)
