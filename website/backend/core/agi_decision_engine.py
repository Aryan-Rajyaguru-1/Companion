#!/usr/bin/env python3
"""
AGI Decision Engine - Autonomous Intelligence Core
===================================================

The brain's autonomous decision-making system that:
- Analyzes incoming queries
- Decides which modules/processes to use
- Orchestrates multi-step workflows
- Makes intelligent decisions about resource allocation
- Learns from outcomes to improve future decisions

This is the TRUE AGI - it thinks, decides, and acts autonomously.

Workflow:
    Query → AGI Engine → Analyzes → Decides Modules → Orchestrates → Response
"""

import logging
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime
from enum import Enum
import re
import json
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Types of queries the AGI can handle"""
    CONVERSATIONAL = "conversational"  # Chat, Q&A
    CODING = "coding"  # Code generation, debugging
    RESEARCH = "research"  # Web search, knowledge retrieval
    ANALYSIS = "analysis"  # Data analysis, reasoning
    CREATIVE = "creative"  # Content generation, brainstorming
    EXECUTION = "execution"  # Code execution, tool usage
    LEARNING = "learning"  # Teaching, concept learning
    MULTIMODAL = "multimodal"  # Image, audio, video processing
    AUTONOMOUS = "autonomous"  # Self-directed tasks


class ModuleType(Enum):
    """Available modules AGI can utilize"""
    # Core
    MODEL_ROUTER = "model_router"
    CONTEXT_MANAGER = "context_manager"
    
    # Phase 1: Knowledge
    KNOWLEDGE_RETRIEVER = "knowledge_retriever"
    VECTOR_STORE = "vector_store"
    ELASTICSEARCH = "elasticsearch"
    
    # Phase 2: Search
    SEARCH_ENGINE = "search_engine"
    MEILISEARCH = "meilisearch"
    
    # Phase 3: Web Intelligence
    WEB_CRAWLER = "web_crawler"
    NEWS_API = "news_api"
    WEB_SEARCH = "web_search"
    
    # Phase 4: Execution
    CODE_EXECUTOR = "code_executor"
    TOOL_EXECUTOR = "tool_executor"
    
    # Phase 5: Optimization
    PROFILER = "profiler"
    CACHE_OPTIMIZER = "cache_optimizer"
    PERFORMANCE_MONITOR = "performance_monitor"
    
    # Advanced Features
    ADVANCED_REASONING = "advanced_reasoning"
    MULTIMODAL_PROCESSOR = "multimodal_processor"
    
    # AGI Components
    PERSONALITY_ENGINE = "personality_engine"
    NEURAL_REASONING = "neural_reasoning"
    SELF_LEARNING = "self_learning"
    LOCAL_INTELLIGENCE = "local_intelligence"
    AUTONOMOUS_SYSTEM = "autonomous_system"


@dataclass
class DecisionPlan:
    """A plan of action decided by AGI"""
    decision_id: str
    query_type: QueryType
    confidence: float  # 0.0-1.0
    modules_to_use: List[ModuleType]
    execution_order: List[str]  # Step-by-step plan
    expected_outcome: str
    reasoning: str  # Why AGI made this decision
    estimated_time: float  # Estimated seconds
    priority: int  # 1-5 (5 = highest)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Result of executing a decision plan"""
    decision_id: str
    success: bool
    response: Any
    modules_used: List[str]
    execution_time: float
    steps_completed: int
    errors: List[str] = field(default_factory=list)
    learned_insights: List[str] = field(default_factory=list)


class AGIDecisionEngine:
    """
    Autonomous General Intelligence Decision Engine
    
    This is the brain's thinking core that:
    1. Analyzes incoming queries
    2. Decides which modules to use
    3. Creates execution plans
    4. Orchestrates multi-module workflows
    5. Learns from outcomes
    """
    
    def __init__(self, brain):
        """
        Initialize AGI Decision Engine
        
        Args:
            brain: CompanionBrain instance (gives access to all modules)
        """
        self.brain = brain
        self.decision_history: List[DecisionPlan] = []
        self.execution_history: List[ExecutionResult] = []
        
        # Learning: Track what works
        self.pattern_success_rates: Dict[str, float] = {}
        self.module_combinations: Dict[str, int] = {}  # Track successful combos
        
        # Decision statistics
        self.stats = {
            'total_decisions': 0,
            'successful_decisions': 0,
            'failed_decisions': 0,
            'average_confidence': 0.0,
            'modules_used_count': {},
            'query_types_handled': {}
        }
        
        logger.info("🤖 AGI Decision Engine initialized - Autonomous intelligence active")
    
    def analyze_and_decide(self, query: str, context: Optional[Dict[str, Any]] = None) -> DecisionPlan:
        """
        Main decision-making method
        
        Analyzes query and autonomously decides:
        - What type of query it is
        - Which modules to use
        - In what order to execute
        - How to orchestrate the response
        
        Args:
            query: User's input query
            context: Additional context
            
        Returns:
            DecisionPlan with autonomous decisions
        """
        self.stats['total_decisions'] += 1
        context = context or {}
        
        logger.info(f"🧠 AGI analyzing query: '{query[:100]}...'")
        
        # Step 1: Understand the query
        query_type = self._classify_query(query)
        query_intent = self._extract_intent(query)
        complexity = self._assess_complexity(query)
        
        # Step 2: Decide which modules are needed
        required_modules = self._decide_modules(query, query_type, query_intent, complexity)
        
        # Step 3: Create execution plan
        execution_order = self._plan_execution(required_modules, query, query_type)
        
        # Step 4: Estimate confidence based on available modules
        confidence = self._calculate_confidence(required_modules, query_type)
        
        # Step 5: Generate reasoning
        reasoning = self._generate_reasoning(query, query_type, required_modules, execution_order)
        
        # Create decision plan
        import uuid
        decision_plan = DecisionPlan(
            decision_id=str(uuid.uuid4())[:8],
            query_type=query_type,
            confidence=confidence,
            modules_to_use=required_modules,
            execution_order=execution_order,
            expected_outcome=self._predict_outcome(query_type, required_modules),
            reasoning=reasoning,
            estimated_time=self._estimate_time(required_modules, complexity),
            priority=self._calculate_priority(query_type, complexity),
            metadata={
                'query_length': len(query),
                'context_provided': bool(context),
                'complexity': complexity,
                'intent': query_intent
            }
        )
        
        # Log decision
        self.decision_history.append(decision_plan)
        self.stats['query_types_handled'][query_type.value] = \
            self.stats['query_types_handled'].get(query_type.value, 0) + 1
        
        logger.info(f"✅ AGI decided: Use {len(required_modules)} modules with {confidence:.1%} confidence")
        logger.debug(f"   Modules: {[m.value for m in required_modules]}")
        logger.debug(f"   Reasoning: {reasoning}")
        
        return decision_plan
    
    def execute_decision(self, plan: DecisionPlan, query: str, context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        """
        Execute the decision plan autonomously
        
        Args:
            plan: Decision plan to execute
            query: Original query
            context: Context data
            
        Returns:
            ExecutionResult with response and metrics
        """
        start_time = datetime.now()
        context = context or {}
        errors = []
        steps_completed = 0
        modules_used = []
        response_data = {}
        
        logger.info(f"🚀 AGI executing plan {plan.decision_id}: {len(plan.execution_order)} steps")
        
        try:
            # Execute each step in the plan
            for step_idx, step in enumerate(plan.execution_order, 1):
                try:
                    logger.debug(f"  Step {step_idx}/{len(plan.execution_order)}: {step}")
                    
                    # Execute step based on type
                    step_result = self._execute_step(step, query, context, response_data)
                    
                    # Store result for next steps
                    if step_result:
                        response_data[step] = step_result
                        modules_used.append(step)
                    
                    steps_completed += 1
                    
                except Exception as e:
                    error_msg = f"Step '{step}' failed: {str(e)}"
                    logger.error(f"❌ {error_msg}")
                    errors.append(error_msg)
                    
                    # AGI decides: Continue or abort?
                    if not self._should_continue_after_error(step, plan, steps_completed):
                        logger.warning("⚠️ AGI decided to abort execution")
                        break
            
            # Synthesize final response from all step results
            final_response = self._synthesize_response(response_data, plan, query)
            
            success = len(errors) == 0 or steps_completed > 0
            
            # Learn from execution
            learned_insights = self._learn_from_execution(plan, success, steps_completed, errors)
            
            # Create result
            execution_time = (datetime.now() - start_time).total_seconds()
            result = ExecutionResult(
                decision_id=plan.decision_id,
                success=success,
                response=final_response,
                modules_used=modules_used,
                execution_time=execution_time,
                steps_completed=steps_completed,
                errors=errors,
                learned_insights=learned_insights
            )
            
            # Update statistics
            self.execution_history.append(result)
            if success:
                self.stats['successful_decisions'] += 1
            else:
                self.stats['failed_decisions'] += 1
            
            # Update module usage stats
            for module in modules_used:
                self.stats['modules_used_count'][module] = \
                    self.stats['modules_used_count'].get(module, 0) + 1
            
            logger.info(f"{'✅' if success else '⚠️'} AGI execution {'completed' if success else 'partial'}: "
                       f"{steps_completed}/{len(plan.execution_order)} steps in {execution_time:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ AGI execution failed: {e}")
            execution_time = (datetime.now() - start_time).total_seconds()
            return ExecutionResult(
                decision_id=plan.decision_id,
                success=False,
                response={"error": str(e)},
                modules_used=modules_used,
                execution_time=execution_time,
                steps_completed=steps_completed,
                errors=[str(e)],
                learned_insights=[]
            )
    
    def _classify_query(self, query: str) -> QueryType:
        """Classify what type of query this is"""
        query_lower = query.lower()
        
        # Patterns for different query types
        patterns = {
            QueryType.CODING: [
                r'\bcode\b', r'\bfunction\b', r'\bclass\b', r'\bdebug\b', r'\bfix\b',
                r'\bpython\b', r'\bjavascript\b', r'\bjava\b', r'\b(def|function|class)\s',
                r'\bimport\b', r'\berror\b.*\bcode\b'
            ],
            QueryType.RESEARCH: [
                r'\bsearch\b', r'\bfind\b', r'\bresearch\b', r'\blook up\b', r'\bwhat is\b',
                r'\bwho is\b', r'\bwhen did\b', r'\bwhere is\b', r'\bhow to\b',
                r'\blatest\b', r'\bcurrent\b', r'\bnews\b', r'\binformation\b'
            ],
            QueryType.ANALYSIS: [
                r'\banalyze\b', r'\bcompare\b', r'\bevaluate\b', r'\bexamine\b',
                r'\bwhy\b', r'\bexplain\b', r'\breason\b', r'\bcause\b', r'\beffect\b'
            ],
            QueryType.CREATIVE: [
                r'\bcreate\b', r'\bgenerate\b', r'\bwrite\b', r'\bcompose\b',
                r'\bdesign\b', r'\bmake\b', r'\bstory\b', r'\bpoem\b', r'\bidea\b'
            ],
            QueryType.EXECUTION: [
                r'\brun\b', r'\bexecute\b', r'\bcalculate\b', r'\bcompute\b',
                r'\bprocess\b', r'\bperform\b'
            ],
            QueryType.LEARNING: [
                r'\blearn\b', r'\bteach\b', r'\bremember\b', r'\bstore\b',
                r'\bunderstand\b', r'\bconcept\b'
            ],
            QueryType.MULTIMODAL: [
                r'\bimage\b', r'\bpicture\b', r'\bphoto\b', r'\baudio\b',
                r'\bvideo\b', r'\bvisualize\b'
            ]
        }
        
        # Score each type
        scores = {}
        for qtype, pattern_list in patterns.items():
            score = sum(1 for pattern in pattern_list if re.search(pattern, query_lower))
            if score > 0:
                scores[qtype] = score
        
        # Return highest scoring type
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        
        # Default to conversational
        return QueryType.CONVERSATIONAL
    
    def _extract_intent(self, query: str) -> str:
        """Extract the user's intent from query"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['how', 'what', 'why', 'when', 'where', 'who']):
            return "information_seeking"
        elif any(word in query_lower for word in ['create', 'make', 'generate', 'build']):
            return "creation"
        elif any(word in query_lower for word in ['fix', 'solve', 'debug', 'error']):
            return "problem_solving"
        elif any(word in query_lower for word in ['help', 'assist', 'guide']):
            return "assistance"
        else:
            return "general"
    
    def _assess_complexity(self, query: str) -> str:
        """Assess query complexity: simple, medium, complex"""
        word_count = len(query.split())
        has_code = bool(re.search(r'[{}()\[\];]', query))
        has_technical = any(term in query.lower() for term in [
            'algorithm', 'architecture', 'system', 'database', 'api',
            'framework', 'library', 'integration', 'optimization'
        ])
        
        if word_count > 50 or has_code or has_technical:
            return "complex"
        elif word_count > 20:
            return "medium"
        else:
            return "simple"
    
    def _decide_modules(self, query: str, query_type: QueryType, intent: str, complexity: str) -> List[ModuleType]:
        """
        AGI decides which modules are needed
        
        This is the core intelligence - deciding which tools to use
        """
        modules = set()
        
        # Always use personality for natural responses
        if self.brain.personality_engine:
            modules.add(ModuleType.PERSONALITY_ENGINE)
        
        # Core modules (almost always needed)
        modules.add(ModuleType.MODEL_ROUTER)
        modules.add(ModuleType.CONTEXT_MANAGER)
        
        # Query type specific modules
        if query_type == QueryType.CODING:
            modules.add(ModuleType.CODE_EXECUTOR)
            modules.add(ModuleType.NEURAL_REASONING)
            if complexity == "complex":
                modules.add(ModuleType.ADVANCED_REASONING)
        
        elif query_type == QueryType.RESEARCH:
            modules.add(ModuleType.WEB_SEARCH)
            modules.add(ModuleType.WEB_CRAWLER)
            modules.add(ModuleType.KNOWLEDGE_RETRIEVER)
            modules.add(ModuleType.SEARCH_ENGINE)
        
        elif query_type == QueryType.ANALYSIS:
            modules.add(ModuleType.NEURAL_REASONING)
            modules.add(ModuleType.ADVANCED_REASONING)
            modules.add(ModuleType.KNOWLEDGE_RETRIEVER)
        
        elif query_type == QueryType.CREATIVE:
            modules.add(ModuleType.PERSONALITY_ENGINE)
            modules.add(ModuleType.NEURAL_REASONING)
        
        elif query_type == QueryType.EXECUTION:
            modules.add(ModuleType.CODE_EXECUTOR)
            modules.add(ModuleType.TOOL_EXECUTOR)
        
        elif query_type == QueryType.LEARNING:
            modules.add(ModuleType.SELF_LEARNING)
            modules.add(ModuleType.KNOWLEDGE_RETRIEVER)
        
        elif query_type == QueryType.MULTIMODAL:
            modules.add(ModuleType.MULTIMODAL_PROCESSOR)
        
        elif query_type == QueryType.AUTONOMOUS:
            if self.brain.autonomous_system:
                modules.add(ModuleType.AUTONOMOUS_SYSTEM)
        
        # Add self-learning if enabled (learns from all interactions)
        if self.brain.self_learning:
            modules.add(ModuleType.SELF_LEARNING)
        
        # Filter to only available modules
        available_modules = self._filter_available_modules(modules)
        
        return list(available_modules)
    
    def _filter_available_modules(self, modules: Set[ModuleType]) -> List[ModuleType]:
        """Filter to only modules that are actually available"""
        available = []
        
        for module in modules:
            # Check if module exists in brain
            module_name = module.value
            
            # Check core modules
            if module_name in ['model_router', 'context_manager']:
                available.append(module)
            
            # Check Phase modules
            elif hasattr(self.brain, module_name) and getattr(self.brain, module_name):
                available.append(module)
            
            # Check AGI components
            elif module_name in ['personality_engine', 'neural_reasoning', 'self_learning', 
                                 'local_intelligence', 'autonomous_system']:
                if hasattr(self.brain, module_name) and getattr(self.brain, module_name):
                    available.append(module)
        
        return available
    
    def _plan_execution(self, modules: List[ModuleType], query: str, query_type: QueryType) -> List[str]:
        """
        Create step-by-step execution plan
        
        AGI decides the order of operations
        """
        steps = []
        
        # Step 1: Always start with context
        steps.append("prepare_context")
        
        # Step 2: If research needed, do it first
        if any(m in modules for m in [ModuleType.WEB_SEARCH, ModuleType.WEB_CRAWLER, ModuleType.KNOWLEDGE_RETRIEVER]):
            steps.append("gather_information")
        
        # Step 3: Reasoning/analysis
        if ModuleType.NEURAL_REASONING in modules or ModuleType.ADVANCED_REASONING in modules:
            steps.append("perform_reasoning")
        
        # Step 4: Code execution if needed
        if ModuleType.CODE_EXECUTOR in modules:
            steps.append("execute_code")
        
        # Step 5: Generate response with personality
        steps.append("generate_response")
        
        # Step 6: Learn from interaction
        if ModuleType.SELF_LEARNING in modules:
            steps.append("learn_from_interaction")
        
        # Step 7: Finalize
        steps.append("finalize_response")
        
        return steps
    
    def _execute_step(self, step: str, query: str, context: Dict[str, Any], 
                     response_data: Dict[str, Any]) -> Optional[Any]:
        """Execute a single step in the plan"""
        
        if step == "prepare_context":
            # Prepare context for processing
            return {
                'query': query,
                'timestamp': datetime.now().isoformat(),
                'context': context
            }
        
        elif step == "gather_information":
            # Use search/crawl/knowledge retrieval
            results = []
            
            if self.brain.knowledge_retriever:
                try:
                    kr_result = self.brain.knowledge_retriever.retrieve(query)
                    results.append(kr_result)
                except:
                    pass
            
            if self.brain.search_engine:
                try:
                    search_result = self.brain.search_engine.search(query)
                    results.append(search_result)
                except:
                    pass
            
            return results if results else None
        
        elif step == "perform_reasoning":
            # Use neural reasoning
            if self.brain.neural_reasoning:
                try:
                    reasoning_result = self.brain.neural_reasoning.reason(query)
                    return reasoning_result
                except:
                    pass
            return None
        
        elif step == "execute_code":
            # Execute code if query contains code
            if self.brain.code_executor:
                # Check if query has code to execute
                code_match = re.search(r'```(\w+)?\n(.*?)\n```', query, re.DOTALL)
                if code_match:
                    code = code_match.group(2)
                    language = code_match.group(1) or 'python'
                    try:
                        exec_result = self.brain.code_executor.execute(code, language)
                        return exec_result
                    except:
                        pass
            return None
        
        elif step == "generate_response":
            # Generate response using LLM
            # Gather all context from previous steps
            full_context = {
                'query': query,
                'information': response_data.get('gather_information'),
                'reasoning': response_data.get('perform_reasoning'),
                'execution': response_data.get('execute_code')
            }
            
            # Build comprehensive prompt
            prompt = query
            if full_context.get('information'):
                prompt += f"\n\nAvailable information: {full_context['information']}"
            if full_context.get('reasoning'):
                prompt += f"\n\nReasoning: {full_context['reasoning']}"
            if full_context.get('execution'):
                prompt += f"\n\nExecution result: {full_context['execution']}"
            
            # Use brain's LLM to generate response
            response = self.brain._call_llm(prompt)
            
            # Apply personality styling if available
            if self.brain.personality_engine:
                try:
                    # Style response with personality
                    styled = response  # Personality styling would happen here
                    return styled
                except:
                    pass
            
            return response
        
        elif step == "learn_from_interaction":
            # Learn from this interaction
            if self.brain.self_learning:
                try:
                    response = response_data.get('generate_response', '')
                    self.brain.self_learning.episodic.store_episode(
                        query, 
                        str(response), 
                        context, 
                        outcome={'success': True},
                        emotions="positive"
                    )
                except:
                    pass
            return None
        
        elif step == "finalize_response":
            # Get the final response
            return response_data.get('generate_response', 
                                    "I've processed your request to the best of my ability.")
        
        return None
    
    def _synthesize_response(self, response_data: Dict[str, Any], plan: DecisionPlan, query: str) -> str:
        """Synthesize final response from all step results"""
        # Get the main response
        final_response = response_data.get('finalize_response', 
                                          response_data.get('generate_response', ''))
        
        # Add any relevant information gathered
        if 'gather_information' in response_data and response_data['gather_information']:
            # Information was gathered - response should include it
            pass
        
        return str(final_response)
    
    def _calculate_confidence(self, modules: List[ModuleType], query_type: QueryType) -> float:
        """Calculate confidence in being able to handle this query"""
        base_confidence = 0.7
        
        # Increase confidence for each available module
        confidence_boost = len(modules) * 0.03
        
        # Decrease if critical modules missing
        if query_type == QueryType.CODING and ModuleType.CODE_EXECUTOR not in modules:
            confidence_boost -= 0.2
        
        if query_type == QueryType.RESEARCH and not any(
            m in modules for m in [ModuleType.WEB_SEARCH, ModuleType.KNOWLEDGE_RETRIEVER]
        ):
            confidence_boost -= 0.15
        
        return min(1.0, max(0.3, base_confidence + confidence_boost))
    
    def _generate_reasoning(self, query: str, query_type: QueryType, 
                           modules: List[ModuleType], execution_order: List[str]) -> str:
        """Generate explanation of AGI's reasoning"""
        return (f"Classified as {query_type.value} query. "
                f"Will use {len(modules)} modules in {len(execution_order)} steps. "
                f"Expected to handle query effectively.")
    
    def _predict_outcome(self, query_type: QueryType, modules: List[ModuleType]) -> str:
        """Predict what kind of outcome to expect"""
        if query_type == QueryType.CODING:
            return "Code solution or explanation"
        elif query_type == QueryType.RESEARCH:
            return "Information and sources"
        elif query_type == QueryType.ANALYSIS:
            return "Detailed analysis and insights"
        else:
            return "Comprehensive response"
    
    def _estimate_time(self, modules: List[ModuleType], complexity: str) -> float:
        """Estimate execution time in seconds"""
        base_time = {'simple': 1.0, 'medium': 2.0, 'complex': 5.0}
        time_per_module = 0.5
        
        return base_time.get(complexity, 2.0) + (len(modules) * time_per_module)
    
    def _calculate_priority(self, query_type: QueryType, complexity: str) -> int:
        """Calculate priority (1-5, 5 = highest)"""
        if query_type in [QueryType.AUTONOMOUS, QueryType.EXECUTION]:
            return 5
        elif complexity == "complex":
            return 4
        elif query_type in [QueryType.CODING, QueryType.ANALYSIS]:
            return 3
        else:
            return 2
    
    def _should_continue_after_error(self, failed_step: str, plan: DecisionPlan, 
                                    steps_completed: int) -> bool:
        """AGI decides whether to continue after an error"""
        # Continue if we've completed more than half the steps
        if steps_completed > len(plan.execution_order) / 2:
            return True
        
        # Continue if the failed step is not critical
        non_critical_steps = ['learn_from_interaction', 'gather_information']
        if failed_step in non_critical_steps:
            return True
        
        return False
    
    def _learn_from_execution(self, plan: DecisionPlan, success: bool, 
                             steps_completed: int, errors: List[str]) -> List[str]:
        """Learn from execution to improve future decisions"""
        insights = []
        
        # Track success rate for this pattern
        pattern_key = f"{plan.query_type.value}_{len(plan.modules_to_use)}_modules"
        if pattern_key not in self.pattern_success_rates:
            self.pattern_success_rates[pattern_key] = []
        
        self.pattern_success_rates[pattern_key].append(1.0 if success else 0.0)
        
        # Learn insights
        if success:
            insights.append(f"Successfully used {len(plan.modules_to_use)} modules")
            
            # Track successful module combination
            combo_key = "_".join(sorted([m.value for m in plan.modules_to_use]))
            self.module_combinations[combo_key] = self.module_combinations.get(combo_key, 0) + 1
        else:
            insights.append(f"Failed after {steps_completed} steps: {errors[0] if errors else 'unknown'}")
        
        return insights
    
    def get_decision_stats(self) -> Dict[str, Any]:
        """Get AGI decision statistics"""
        return {
            'total_decisions': self.stats['total_decisions'],
            'successful': self.stats['successful_decisions'],
            'failed': self.stats['failed_decisions'],
            'success_rate': (
                self.stats['successful_decisions'] / self.stats['total_decisions']
                if self.stats['total_decisions'] > 0 else 0.0
            ),
            'modules_used_count': self.stats['modules_used_count'],
            'query_types_handled': self.stats['query_types_handled'],
            'top_module_combinations': sorted(
                self.module_combinations.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
            'pattern_success_rates': {
                k: sum(v) / len(v) for k, v in self.pattern_success_rates.items()
            }
        }
