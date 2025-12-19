#!/usr/bin/env python3
"""
AGI Orchestrator - Coordinates Complex Multi-Agent Tasks
==========================================================

The AGI Orchestrator is the master coordinator that:
- Breaks down complex tasks into manageable subtasks
- Assigns subtasks to appropriate specialized agents
- Orchestrates execution across multiple agents
- Aggregates results from different agents
- Handles inter-agent communication and dependencies
- Learns from successful task completions

This enables true AGI behavior by coordinating multiple specialized
AI agents to work together on complex problems.
"""

import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime
from enum import Enum
import json
import hashlib
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class TaskComplexity(Enum):
    """Task complexity levels"""
    SIMPLE = "simple"      # Single agent can handle
    MODERATE = "moderate"  # 2-3 agents needed
    COMPLEX = "complex"    # 4+ agents, multiple steps
    EXPERT = "expert"      # Requires specialized knowledge


class TaskType(Enum):
    """Types of tasks the orchestrator can handle"""
    RESEARCH = "research"
    CODING = "coding"
    ANALYSIS = "analysis"
    CREATIVE = "creative"
    EXECUTION = "execution"
    OPTIMIZATION = "optimization"
    LEARNING = "learning"
    INTEGRATION = "integration"


@dataclass
class SubTask:
    """Represents a subtask in a complex task"""
    id: str
    description: str
    task_type: TaskType
    complexity: TaskComplexity
    dependencies: List[str] = field(default_factory=list)
    assigned_agent: Optional[str] = None
    status: str = "pending"
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestrationResult:
    """Result of an orchestrated task"""
    task_id: str
    success: bool
    final_result: str
    subtasks: List[SubTask]
    total_time: float
    agents_used: Set[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


class AGIOrchestrator:
    """
    Master orchestrator for complex multi-agent tasks.

    Coordinates multiple specialized agents to work together on complex problems
    that no single agent could solve alone.
    """

    def __init__(self, brain, agent_registry: Dict[str, Any]):
        """
        Initialize the AGI Orchestrator

        Args:
            brain: The main CompanionBrain instance
            agent_registry: Dictionary mapping agent names to agent instances
        """
        self.brain = brain
        self.agents = agent_registry
        self.task_history: List[OrchestrationResult] = []
        self.executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="agi_orchestrator")

        # Learning data
        self.success_patterns = {}
        self.failure_patterns = {}

        logger.info("🧠 AGI Orchestrator initialized with {} agents".format(len(agent_registry)))

    def orchestrate_task(self, task: str, context: Optional[Dict[str, Any]] = None) -> OrchestrationResult:
        """
        Orchestrate a complex task across multiple agents

        Args:
            task: The complex task description
            context: Additional context for the task

        Returns:
            OrchestrationResult with final result and metadata
        """
        start_time = datetime.now()
        task_id = hashlib.sha256(f"{task}{start_time.isoformat()}".encode()).hexdigest()[:16]

        logger.info(f"🎯 Starting orchestrated task {task_id}: {task[:100]}...")

        try:
            # Phase 1: Task Analysis & Decomposition
            subtasks = self._analyze_and_decompose_task(task, context or {})

            if len(subtasks) <= 1:
                # Simple task - handle directly
                logger.info("📝 Task is simple, handling directly")
                result = self.brain.ask(task)
                return OrchestrationResult(
                    task_id=task_id,
                    success=True,
                    final_result=result,
                    subtasks=[],
                    total_time=(datetime.now() - start_time).total_seconds(),
                    agents_used={"brain"}
                )

            # Phase 2: Agent Assignment
            self._assign_agents_to_subtasks(subtasks)

            # Phase 3: Dependency Resolution
            execution_order = self._resolve_dependencies(subtasks)

            # Phase 4: Parallel Execution
            completed_subtasks = self._execute_subtasks_parallel(subtasks, execution_order)

            # Phase 5: Result Aggregation
            final_result = self._aggregate_results(completed_subtasks, task)

            # Phase 6: Learning
            self._learn_from_execution(task, subtasks, final_result)

            total_time = (datetime.now() - start_time).total_seconds()
            agents_used = {st.assigned_agent for st in completed_subtasks if st.assigned_agent}

            result = OrchestrationResult(
                task_id=task_id,
                success=True,
                final_result=final_result,
                subtasks=completed_subtasks,
                total_time=total_time,
                agents_used=agents_used,
                metadata={
                    "decomposition_time": 0,  # Could track this
                    "execution_time": total_time,
                    "parallelization_factor": len(agents_used)
                }
            )

            self.task_history.append(result)
            logger.info(f"✅ Orchestrated task {task_id} completed in {total_time:.2f}s using {len(agents_used)} agents")

            return result

        except Exception as e:
            logger.error(f"❌ Orchestration failed for task {task_id}: {e}")
            return OrchestrationResult(
                task_id=task_id,
                success=False,
                final_result=f"Orchestration failed: {str(e)}",
                subtasks=[],
                total_time=(datetime.now() - start_time).total_seconds(),
                agents_used=set(),
                metadata={"error": str(e)}
            )

    def _analyze_and_decompose_task(self, task: str, context: Dict[str, Any]) -> List[SubTask]:
        """
        Analyze the task and break it down into subtasks

        Uses the brain to intelligently decompose complex tasks
        """
        logger.info("🔍 Analyzing and decomposing task...")

        # Create decomposition prompt
        decomposition_prompt = f"""
        Analyze this complex task and break it down into specific, actionable subtasks:

        TASK: {task}

        CONTEXT: {json.dumps(context, indent=2) if context else "None"}

        REQUIREMENTS:
        1. Break down into 3-8 specific subtasks
        2. Each subtask should be independently solvable
        3. Identify dependencies between subtasks
        4. Estimate complexity (simple/moderate/complex/expert)
        5. Suggest appropriate agent type for each subtask

        Return JSON format:
        {{
            "subtasks": [
                {{
                    "id": "unique_id",
                    "description": "detailed description",
                    "type": "research|coding|analysis|creative|execution|optimization|learning|integration",
                    "complexity": "simple|moderate|complex|expert",
                    "dependencies": ["subtask_id1", "subtask_id2"],
                    "estimated_effort": "low|medium|high"
                }}
            ]
        }}
        """

        try:
            response = self.brain.ask(decomposition_prompt, system="You are an expert task decomposition specialist")
            parsed = json.loads(response)

            subtasks = []
            for st_data in parsed.get("subtasks", []):
                subtask = SubTask(
                    id=st_data["id"],
                    description=st_data["description"],
                    task_type=TaskType(st_data["type"]),
                    complexity=TaskComplexity(st_data["complexity"]),
                    dependencies=st_data.get("dependencies", []),
                    metadata={"estimated_effort": st_data.get("estimated_effort", "medium")}
                )
                subtasks.append(subtask)

            logger.info(f"✅ Decomposed into {len(subtasks)} subtasks")
            return subtasks

        except Exception as e:
            logger.warning(f"❌ Task decomposition failed: {e}, using fallback")
            # Fallback: create basic subtasks
            return [
                SubTask(
                    id="analyze",
                    description=f"Analyze the task: {task}",
                    task_type=TaskType.ANALYSIS,
                    complexity=TaskComplexity.SIMPLE
                ),
                SubTask(
                    id="execute",
                    description=f"Execute the main task: {task}",
                    task_type=TaskType.EXECUTION,
                    complexity=TaskComplexity.MODERATE,
                    dependencies=["analyze"]
                ),
                SubTask(
                    id="verify",
                    description="Verify the results and ensure quality",
                    task_type=TaskType.ANALYSIS,
                    complexity=TaskComplexity.SIMPLE,
                    dependencies=["execute"]
                )
            ]

    def _assign_agents_to_subtasks(self, subtasks: List[SubTask]):
        """
        Assign appropriate agents to each subtask based on type and complexity
        """
        logger.info("👥 Assigning agents to subtasks...")

        # Agent capabilities mapping
        agent_capabilities = {
            "research": ["research", "analysis"],
            "code": ["coding", "execution", "optimization"],
            "review": ["analysis", "learning"],
            "creative": ["creative", "integration"],
            "default": ["conversational", "learning"]  # fallback
        }

        for subtask in subtasks:
            # Find best agent for this subtask type
            best_agent = "default"

            for agent_name, capabilities in agent_capabilities.items():
                if subtask.task_type.value in capabilities:
                    if agent_name in self.agents:
                        best_agent = agent_name
                        break

            subtask.assigned_agent = best_agent
            logger.debug(f"  Assigned {best_agent} to subtask {subtask.id}")

    def _resolve_dependencies(self, subtasks: List[SubTask]) -> List[List[str]]:
        """
        Resolve subtask dependencies and create execution order

        Returns list of lists, where each inner list contains subtasks
        that can be executed in parallel
        """
        logger.info("🔗 Resolving dependencies...")

        # Create dependency graph
        completed = set()
        execution_stages = []

        remaining = {st.id: st for st in subtasks}

        while remaining:
            # Find subtasks with all dependencies satisfied
            stage = []
            for st_id, st in list(remaining.items()):
                if all(dep in completed for dep in st.dependencies):
                    stage.append(st_id)

            if not stage:
                # Circular dependency or impossible situation
                logger.warning("⚠️ Dependency resolution issue, executing remaining tasks")
                stage = list(remaining.keys())

            # Add stage to execution order
            execution_stages.append(stage)

            # Mark as completed and remove from remaining
            for st_id in stage:
                completed.add(st_id)
                del remaining[st_id]

        logger.info(f"✅ Resolved into {len(execution_stages)} execution stages")
        return execution_stages

    def _execute_subtasks_parallel(self, subtasks: List[SubTask], execution_order: List[List[str]]) -> List[SubTask]:
        """
        Execute subtasks in parallel respecting dependencies
        """
        logger.info("🚀 Executing subtasks...")

        subtask_dict = {st.id: st for st in subtasks}

        for stage_idx, stage in enumerate(execution_order, 1):
            logger.info(f"  Stage {stage_idx}/{len(execution_order)}: {len(stage)} subtasks")

            if len(stage) == 1:
                # Single subtask - execute directly
                st_id = stage[0]
                subtask = subtask_dict[st_id]
                self._execute_single_subtask(subtask)
            else:
                # Multiple subtasks - execute in parallel
                futures = []
                for st_id in stage:
                    subtask = subtask_dict[st_id]
                    future = self.executor.submit(self._execute_single_subtask, subtask)
                    futures.append(future)

                # Wait for all in this stage to complete
                for future in as_completed(futures):
                    try:
                        future.result()  # Will raise exception if subtask failed
                    except Exception as e:
                        logger.error(f"❌ Subtask execution error: {e}")

        return subtasks

    def _execute_single_subtask(self, subtask: SubTask):
        """
        Execute a single subtask using the assigned agent
        """
        start_time = datetime.now()

        try:
            subtask.status = "running"
            logger.info(f"  Executing subtask {subtask.id}: {subtask.description[:50]}...")

            # Get the assigned agent
            agent_name = subtask.assigned_agent or "default"
            agent = self.agents.get(agent_name)
            if not agent:
                raise ValueError(f"Agent {subtask.assigned_agent} not found")

            # Execute the subtask
            if hasattr(agent, 'execute'):
                result = agent.execute(subtask.description)
            elif hasattr(agent, 'ask'):
                result = agent.ask(subtask.description)
            else:
                # Fallback to brain
                result = self.brain.ask(subtask.description)

            subtask.result = result
            subtask.status = "completed"
            subtask.execution_time = (datetime.now() - start_time).total_seconds()

            logger.info(f"  ✅ Subtask {subtask.id} completed in {subtask.execution_time:.2f}s")

        except Exception as e:
            subtask.status = "failed"
            subtask.error = str(e)
            subtask.execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"  ❌ Subtask {subtask.id} failed: {e}")

    def _aggregate_results(self, subtasks: List[SubTask], original_task: str) -> str:
        """
        Aggregate results from all subtasks into a coherent final result
        """
        logger.info("📋 Aggregating results...")

        # Collect successful results
        successful_results = []
        for st in subtasks:
            if st.status == "completed" and st.result:
                successful_results.append({
                    "subtask": st.description,
                    "result": st.result,
                    "agent": st.assigned_agent
                })

        if not successful_results:
            return "No subtasks completed successfully"

        # Create aggregation prompt
        context = "\n\n".join([
            f"Subtask: {r['subtask']}\nAgent: {r['agent']}\nResult: {r['result']}"
            for r in successful_results
        ])

        aggregation_prompt = f"""
        Original Task: {original_task}

        Subtask Results:
        {context}

        Synthesize all these results into a comprehensive, coherent final answer.
        Make sure the response addresses the original task completely and effectively.
        """

        try:
            final_result = self.brain.ask(aggregation_prompt, system="You are an expert at synthesizing information from multiple sources")
            logger.info("✅ Results aggregated successfully")
            return final_result
        except Exception as e:
            logger.error(f"❌ Result aggregation failed: {e}")
            # Fallback: concatenate results
            return "\n\n".join([r['result'] for r in successful_results])

    def _learn_from_execution(self, task: str, subtasks: List[SubTask], final_result: str):
        """
        Learn from successful task execution to improve future orchestrations
        """
        try:
            # Analyze what worked well
            successful_subtasks = [st for st in subtasks if st.status == "completed"]
            failed_subtasks = [st for st in subtasks if st.status == "failed"]

            if successful_subtasks:
                # Record successful patterns
                pattern_key = f"{len(subtasks)}_{len(successful_subtasks)}"
                if pattern_key not in self.success_patterns:
                    self.success_patterns[pattern_key] = 0
                self.success_patterns[pattern_key] += 1

                # Learn agent assignments
                for st in successful_subtasks:
                    agent_key = f"{st.task_type.value}_{st.assigned_agent}"
                    # Could store in a learning database

            if failed_subtasks:
                # Record failure patterns for future avoidance
                for st in failed_subtasks:
                    failure_key = f"{st.task_type.value}_{st.error or 'unknown'}"
                    if failure_key not in self.failure_patterns:
                        self.failure_patterns[failure_key] = 0
                    self.failure_patterns[failure_key] += 1

        except Exception as e:
            logger.debug(f"Learning update failed: {e}")

    def get_orchestration_stats(self) -> Dict[str, Any]:
        """
        Get statistics about orchestration performance
        """
        if not self.task_history:
            return {"total_tasks": 0}

        total_tasks = len(self.task_history)
        successful_tasks = sum(1 for t in self.task_history if t.success)
        avg_time = sum(t.total_time for t in self.task_history) / total_tasks
        avg_agents = sum(len(t.agents_used) for t in self.task_history) / total_tasks

        return {
            "total_tasks": total_tasks,
            "success_rate": successful_tasks / total_tasks,
            "average_time": avg_time,
            "average_agents_used": avg_agents,
            "success_patterns": self.success_patterns,
            "failure_patterns": self.failure_patterns
        }

    def shutdown(self):
        """
        Clean shutdown of the orchestrator
        """
        logger.info("🛑 Shutting down AGI Orchestrator...")
        self.executor.shutdown(wait=True)
        logger.info("✅ AGI Orchestrator shut down")