#!/usr/bin/env python3
"""
Advanced Brain Wrapper
=====================

Unified interface combining all advanced features:
- Advanced Reasoning
- Multi-modal Processing
- Streaming Responses
- Memory Persistence
- Agent Coordination
- Real-time Learning
- Model Fine-tuning
- Long-term Memory
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Callable, AsyncGenerator

# Import all advanced systems
from .advanced_reasoning import AdvancedReasoningSystem, ReasoningStrategy
from .multimodal import MultiModalSystem, MediaInput, ModalityType
from .streaming import StreamingSystem, StreamController, StreamChunk
from .memory_persistence import MemoryPersistenceSystem, MemoryType
from .agent_coordination import AgentCoordinationSystem, AgentRole
from .realtime_learning import RealtimeLearningSystem, FeedbackType
from .model_finetuning import ModelFinetuningSystem, FineTuneConfig, FinetuningMethod
from .longterm_memory import LongtermMemorySystem, MemoryLevel

logger = logging.getLogger(__name__)


class AdvancedBrainWrapper:
    """
    Unified Advanced Brain System
    Combines all 8 advanced capabilities
    """
    
    def __init__(self, llm_function: Callable, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Advanced Brain
        
        Args:
            llm_function: Base LLM function
            config: Optional configuration
        """
        self.llm_function = llm_function
        self.config = config or {}
        
        logger.info("🚀 Initializing Advanced Brain System...")
        
        # Initialize all systems
        self.reasoning = AdvancedReasoningSystem()
        self.multimodal = MultiModalSystem()
        self.streaming = StreamingSystem()
        self.memory = MemoryPersistenceSystem()
        self.agents = AgentCoordinationSystem(llm_function)
        self.learning = RealtimeLearningSystem()
        self.finetuning = ModelFinetuningSystem()
        self.longterm_memory = LongtermMemorySystem(llm_function)
        
        # Setup default agents
        self._setup_default_agents()
        
        # Track usage
        self.usage_stats = {
            "total_queries": 0,
            "reasoning_used": 0,
            "multimodal_used": 0,
            "streaming_used": 0,
            "agents_used": 0
        }
        
        logger.info("✅ Advanced Brain System initialized with all 8 capabilities")
    
    def _setup_default_agents(self):
        """Setup default specialized agents"""
        self.agents.create_agent(
            name="Research Assistant",
            role=AgentRole.RESEARCHER,
            capabilities=["research", "information_gathering", "fact_checking"]
        )
        
        self.agents.create_agent(
            name="Data Analyzer",
            role=AgentRole.ANALYZER,
            capabilities=["analysis", "insights", "data_processing"]
        )
        
        self.agents.create_agent(
            name="Task Planner",
            role=AgentRole.PLANNER,
            capabilities=["planning", "strategy", "organization"]
        )
        
        self.agents.create_agent(
            name="Quality Critic",
            role=AgentRole.CRITIC,
            capabilities=["evaluation", "quality_check", "critique"]
        )
    
    # ============================================================
    # HIGH-LEVEL UNIFIED INTERFACE
    # ============================================================
    
    async def think(
        self,
        query: str,
        user_id: str = "default",
        use_reasoning: bool = True,
        use_memory: bool = True,
        use_agents: bool = False,
        stream: bool = False,
        media_inputs: Optional[List[MediaInput]] = None
    ) -> Any:
        """
        Unified thinking interface
        
        Args:
            query: User query
            user_id: User identifier
            use_reasoning: Use advanced reasoning
            use_memory: Use memory systems
            use_agents: Use multi-agent coordination
            stream: Stream response
            media_inputs: Optional media inputs
            
        Returns:
            Response (string or stream)
        """
        self.usage_stats["total_queries"] += 1
        
        # Step 1: Process media if provided
        if media_inputs:
            self.usage_stats["multimodal_used"] += 1
            media_results = self.multimodal.process(
                media_inputs,
                query,
                vision_llm=self.llm_function
            )
            
            # Augment query with media insights
            media_context = "\n".join([
                f"[{r.type.value}]: {r.content}"
                for r in media_results
            ])
            query = f"{query}\n\nMedia Context:\n{media_context}"
        
        # Step 2: Retrieve relevant memory
        context = ""
        if use_memory:
            # Get long-term context
            lt_context = self.longterm_memory.retrieve_context(query)
            if lt_context:
                context += f"Long-term Context:\n{lt_context}\n\n"
            
            # Get conversation history
            conv_context = self.memory.get_context(user_id, limit=5)
            if conv_context:
                context += f"Recent Conversation:\n{conv_context}\n\n"
        
        # Step 3: Add context to query
        if context:
            query = f"{context}Query: {query}"
        
        # Step 4: Process with reasoning or agents
        if use_agents:
            self.usage_stats["agents_used"] += 1
            result = await self.agents.execute_task(
                description=query,
                decompose=True,
                use_multiple_agents=True
            )
        elif use_reasoning:
            self.usage_stats["reasoning_used"] += 1
            reasoning_result = self.reasoning.reason(
                query=query,
                strategy="auto"
            )
            result = reasoning_result.final_answer
        else:
            result = self.llm_function(query)
        
        # Step 5: Store in memory
        if use_memory:
            # Add to working memory
            self.longterm_memory.add_to_working_memory(
                content=f"Q: {query}\nA: {result}",
                importance=0.6
            )
            
            # Record interaction
            self.memory.add_interaction(
                user_id=user_id,
                user_message=query,
                assistant_response=result
            )
            
            # Track for learning
            self.learning.track_interaction(
                user_id=user_id,
                query=query,
                response=result
            )
        
        # Step 6: Return (stream or complete)
        if stream:
            self.usage_stats["streaming_used"] += 1
            return self._stream_response(result)
        else:
            return result
    
    async def _stream_response(self, content: str) -> AsyncGenerator[StreamChunk, None]:
        """Stream a response"""
        async for chunk in self.streaming.stream_response(content, stream_type="token"):
            yield chunk
    
    # ============================================================
    # ADVANCED REASONING
    # ============================================================
    
    def reason(
        self,
        query: str,
        strategy: str = "auto",
        user_id: str = "default"
    ) -> Dict[str, Any]:
        """
        Advanced reasoning
        
        Args:
            query: Query to reason about
            strategy: Reasoning strategy
            user_id: User identifier
            
        Returns:
            Reasoning result with steps
        """
        result = self.reasoning.reason(
            query=query,
            strategy=strategy,
            llm_function=self.llm_function
        )
        
        # Store reasoning in long-term memory
        self.longterm_memory.store_longterm(
            content=f"Reasoning: {query}",
            summary=result.final_answer,
            importance=0.7
        )
        
        return {
            "strategy": result.strategy,
            "steps": [s.__dict__ for s in result.steps],
            "answer": result.final_answer,
            "confidence": result.total_confidence
        }
    
    # ============================================================
    # MULTI-MODAL PROCESSING
    # ============================================================
    
    def process_media(
        self,
        media_inputs: List[MediaInput],
        prompt: str,
        user_id: str = "default"
    ) -> List[Dict[str, Any]]:
        """
        Process multi-modal inputs
        
        Args:
            media_inputs: List of media inputs
            prompt: Processing prompt
            user_id: User identifier
            
        Returns:
            List of processing results
        """
        results = self.multimodal.process(
            media_inputs,
            prompt,
            vision_llm=self.llm_function
        )
        
        # Store in memory
        for result in results:
            self.memory.remember(
                user_id=user_id,
                content=f"Processed {result.type.value}: {result.content}",
                memory_type="semantic",
                importance=0.6
            )
        
        return [r.__dict__ for r in results]
    
    # ============================================================
    # STREAMING
    # ============================================================
    
    async def stream_think(
        self,
        query: str,
        user_id: str = "default",
        show_reasoning: bool = True
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream thinking process
        
        Args:
            query: Query to process
            user_id: User identifier
            show_reasoning: Show reasoning steps
            
        Yields:
            Stream chunks
        """
        controller = self.streaming.create_controller()
        
        async for chunk in self.streaming.stream_with_thinking(
            llm_stream_function=lambda q: self._mock_stream(q),
            query=query,
            show_reasoning=show_reasoning,
            controller=controller
        ):
            yield {
                "event": chunk.event.value,
                "content": chunk.content,
                "metadata": chunk.metadata,
                "timestamp": chunk.timestamp
            }
    
    async def _mock_stream(self, query: str):
        """Mock LLM stream (replace with actual streaming LLM)"""
        response = self.llm_function(query)
        async for chunk in self.streaming.stream_response(response):
            yield chunk
    
    # ============================================================
    # AGENT COORDINATION
    # ============================================================
    
    async def delegate_task(
        self,
        task: str,
        use_multiple_agents: bool = True,
        decompose: bool = True
    ) -> str:
        """
        Delegate task to agents
        
        Args:
            task: Task description
            use_multiple_agents: Use multiple agents
            decompose: Decompose into subtasks
            
        Returns:
            Task result
        """
        result = await self.agents.execute_task(
            description=task,
            decompose=decompose,
            use_multiple_agents=use_multiple_agents
        )
        return str(result)
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all agents"""
        return self.agents.get_agent_status()
    
    # ============================================================
    # LEARNING & FEEDBACK
    # ============================================================
    
    def provide_feedback(
        self,
        user_id: str,
        interaction_id: str,
        feedback_type: str,
        value: Any
    ):
        """
        Provide feedback for learning
        
        Args:
            user_id: User identifier
            interaction_id: Interaction ID
            feedback_type: Type of feedback
            value: Feedback value
        """
        self.learning.provide_feedback(
            user_id=user_id,
            interaction_id=interaction_id,
            feedback_type=feedback_type,
            value=value
        )
    
    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get learned user profile"""
        return self.learning.get_user_profile(user_id)
    
    def get_adaptations(self) -> List[str]:
        """Get current system adaptations"""
        return self.learning.get_adaptations()
    
    # ============================================================
    # MODEL FINE-TUNING
    # ============================================================
    
    def prepare_training_data(
        self,
        user_id: str,
        min_quality: float = 0.8
    ) -> int:
        """
        Prepare training data from user interactions
        
        Args:
            user_id: User identifier
            min_quality: Minimum quality score
            
        Returns:
            Number of training examples prepared
        """
        # Get conversation history
        conversations = self.memory.get_conversation(user_id, limit=100)
        
        # Convert to training examples
        interactions = []
        for i in range(0, len(conversations) - 1, 2):
            if i + 1 < len(conversations):
                user_msg = conversations[i]
                asst_msg = conversations[i + 1]
                if user_msg[0] == "user" and asst_msg[0] == "assistant":
                    interactions.append((user_msg[1], asst_msg[1]))
        
        return self.finetuning.prepare_training_data(interactions)
    
    def get_training_stats(self) -> Dict[str, Any]:
        """Get training dataset statistics"""
        return self.finetuning.get_dataset_stats()
    
    # ============================================================
    # MEMORY MANAGEMENT
    # ============================================================
    
    def remember(
        self,
        user_id: str,
        content: str,
        memory_type: str = "long_term",
        importance: float = 0.7
    ):
        """
        Store memory
        
        Args:
            user_id: User identifier
            content: Content to remember
            memory_type: Type of memory
            importance: Importance score
        """
        # Store in memory persistence
        self.memory.remember(
            user_id=user_id,
            content=content,
            memory_type=memory_type,
            importance=importance
        )
        
        # Also store in long-term memory
        if importance >= 0.8:
            self.longterm_memory.store_longterm(
                content=content,
                importance=importance
            )
    
    def recall(self, user_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Recall memories
        
        Args:
            user_id: User identifier
            query: Search query
            limit: Maximum results
            
        Returns:
            List of memories
        """
        memories = self.memory.recall(user_id, query, limit)
        return [m.__dict__ for m in memories]
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory system statistics"""
        return {
            "persistence": self.memory.get_context("default", limit=1) != "",
            "longterm": self.longterm_memory.get_memory_stats()
        }
    
    # ============================================================
    # SYSTEM STATUS & CAPABILITIES
    # ============================================================
    
    def get_capabilities(self) -> Dict[str, bool]:
        """Get enabled capabilities"""
        return {
            "advanced_reasoning": self.reasoning.enabled,
            "multimodal": self.multimodal.enabled,
            "streaming": self.streaming.enabled,
            "memory_persistence": self.memory.enabled,
            "agent_coordination": self.agents.enabled,
            "realtime_learning": self.learning.enabled,
            "model_finetuning": self.finetuning.enabled,
            "longterm_memory": self.longterm_memory.enabled
        }
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        return {
            "capabilities": self.get_capabilities(),
            "usage_stats": self.usage_stats,
            "multimodal_available": self.multimodal.get_capabilities(),
            "agents": self.agents.get_agent_status(),
            "memory": self.get_memory_stats()
        }
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return self.usage_stats.copy()


# Convenience function
def create_advanced_brain(
    llm_function: Callable,
    config: Optional[Dict[str, Any]] = None
) -> AdvancedBrainWrapper:
    """
    Create Advanced Brain System
    
    Args:
        llm_function: Base LLM function
        config: Optional configuration
        
    Returns:
        AdvancedBrainWrapper instance
    """
    return AdvancedBrainWrapper(llm_function, config)
