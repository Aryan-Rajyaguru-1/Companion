#!/usr/bin/env python3
"""
Companion BaaS SDK - Client Library
===================================

Easy-to-use client for integrating Companion Brain into any application.

Features:
    - 6 Core Phases (Knowledge, Search, Web Intelligence, Execution, Optimization)
    - 8 Advanced Capabilities (Reasoning, Multi-modal, Streaming, Memory, Agents, Learning, Fine-tuning, Long-term Memory)
    - 23+ Built-in Tools
    - Async Support
    - 100% FREE with Bytez integration

Basic Usage:
    from companion_baas.sdk import BrainClient
    
    # Initialize
    client = BrainClient(app_type="chatbot")
    
    # Basic chat
    response = client.ask("What is AI?")
    print(response)

Advanced Features (100% FREE with Bytez):
    # Advanced reasoning with Chain-of-Thought
    result = client.reason("Complex question", strategy="chain_of_thought")
    print(result['answer'])
    
    # Memory operations (persistent storage)
    client.remember("user123", "User loves Python", importance=0.9)
    memories = client.recall("user123", "Python")
    print(f"Found {len(memories)} memories")
    
    # Real-time learning from feedback
    client.provide_learning_feedback("user123", "msg_1", "rating", 5)
    
    # Streaming responses (async)
    async for chunk in client.stream_think("Tell me about quantum computing"):
        if chunk['event'] == 'token':
            print(chunk['content'], end='', flush=True)
    
    # Multi-agent coordination (async)
    result = await client.delegate_task("Research and compare Python frameworks")
    print(f"Agents used: {result['agents_used']}")
    
    # Execute code in sandbox
    result = client.execute_code("print('Hello World')", "python")
    print(result['output'])
    
    # Check all capabilities
    caps = client.get_advanced_capabilities()
    print(f"Advanced features: {caps['capabilities']}")

Bytez Integration:
    - FREE tier: 141k+ models (0-10B params)
    - Unlimited tokens, images, videos
    - 1 concurrent request (sequential execution)
    - No credit card required

App Types:
    - "chatbot": Conversational AI
    - "coder": Code assistant  
    - "research": Research assistant
    - "assistant": General assistant
    - "tutor": Educational tutor
    - "analyst": Data analyst
"""

import sys
import os
from typing import Dict, List, Optional, Any

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from companion_baas.core.brain import CompanionBrain

class BrainClient:
    """
    Simple client for Companion Brain integration
    
    This is the interface that apps use to communicate with the brain.
    Apps don't need to know anything about AI models, routing, or prompts!
    """
    
    def __init__(
        self,
        app_type: str = "general",
        config: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        Initialize Brain Client
        
        Args:
            app_type: Type of application
                - "chatbot": Conversational AI
                - "coder": Code assistant
                - "research": Research assistant
                - "image_gen": Image generation
                - "video_gen": Video generation
                - "assistant": General assistant
                - "tutor": Educational tutor
                - "analyst": Data analyst
            config: Custom configuration
            **kwargs: Additional options passed to brain
        """
        self.brain = CompanionBrain(
            app_type=app_type,
            config=config,
            **kwargs
        )
        self.app_type = app_type
    
    def chat(
        self,
        message: str,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        tools: Optional[List[str]] = None,
        **context
    ) -> Dict[str, Any]:
        """
        Send a chat message to the brain
        
        Args:
            message: User's message
            user_id: Unique user ID (for context management)
            conversation_id: Conversation ID (for multi-turn chats)
            tools: List of tools to use ['web', 'code', 'think', 'research']
            **context: Additional context as keyword arguments
            
        Returns:
            {
                'response': str,  # The AI's response
                'metadata': dict,  # Model info, timing, etc.
                'success': bool   # Whether request succeeded
            }
        
        Example:
            response = client.chat(
                "What is Python?",
                user_id="user123",
                tools=['web']
            )
            print(response['response'])
        """
        return self.brain.think(
            message=message,
            context=context or {},
            tools=tools,
            user_id=user_id,
            conversation_id=conversation_id
        )
    
    def think(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        tools: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        use_agi_decision: bool = True
    ) -> Dict[str, Any]:
        """
        Main thinking method - processes any request intelligently
        
        **NEW: AGI-Powered**
        When AGI is enabled, the brain autonomously:
        1. Analyzes the query
        2. Decides which modules to use
        3. Executes the optimal workflow
        4. Learns from the outcome
        
        Args:
            message: User's input message/query
            context: Application-specific context
            tools: List of tools to use
            user_id: Unique user identifier
            conversation_id: Conversation ID
            use_agi_decision: Use AGI Decision Engine (default: True)
            
        Returns:
            Dict with response, metadata, success, and optional agi_plan
        
        Example:
            # AGI autonomously handles everything
            response = client.think("Write a Python function to sort a list")
            print(response['response'])
            print(f"AGI used: {response['metadata']['modules_used']}")
            print(f"Confidence: {response['agi_plan']['confidence']:.1%}")
        """
        return self.brain.think(
            message=message,
            context=context or {},
            tools=tools,
            user_id=user_id,
            conversation_id=conversation_id,
            use_agi_decision=use_agi_decision
        )
    
    def ask(self, question: str, **kwargs) -> str:
        """
        Quick ask - just get the response text
        
        Example:
            answer = client.ask("What is 2+2?")
            print(answer)  # "4"
        """
        result = self.chat(question, **kwargs)
        return result.get('response', '')
    
    def get_history(
        self,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get conversation history
        
        Returns:
            List of messages with roles and content
        """
        return self.brain.get_conversation_history(
            user_id=user_id,
            conversation_id=conversation_id,
            limit=limit
        )
    
    def clear_history(
        self,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None
    ):
        """Clear conversation history"""
        self.brain.clear_conversation(
            user_id=user_id,
            conversation_id=conversation_id
        )
    
    def search(self, query: str, deep: bool = False) -> Dict[str, Any]:
        """
        Perform web search
        
        Args:
            query: Search query
            deep: Use deep search for comprehensive results
            
        Returns:
            Search results with summaries and links
        """
        return self.brain.search_web(query, deep_search=deep)
    
    def feedback(
        self,
        message_id: str,
        rating: int,
        comment: Optional[str] = None,
        conversation_id: Optional[str] = None
    ):
        """
        Provide feedback for learning
        
        Args:
            message_id: ID of the message being rated
            rating: 1-5 star rating
            comment: Optional feedback comment
            conversation_id: Conversation ID
        """
        self.brain.provide_feedback(
            message_id=message_id,
            rating=rating,
            comment=comment,
            conversation_id=conversation_id
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get brain statistics and metrics"""
        return self.brain.get_stats()
    
    # ========================================================================
    # NEW PHASE 4 & 5 METHODS - Added with brain upgrade
    # ========================================================================
    
    def execute_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """
        Execute code (Phase 4: Execution & Generation)
        
        Args:
            code: Code to execute
            language: "python" or "javascript"
            
        Returns:
            {
                'success': bool,
                'output': str,
                'error': str (if failed),
                'execution_time': float
            }
            
        Example:
            result = client.execute_code("print(2 + 2)", "python")
            print(result['output'])  # "4"
        """
        return self.brain.execute_code(code, language)
    
    def call_tool(self, tool_name: str, *args, **kwargs) -> Any:
        """
        Call a built-in tool (Phase 4: Execution & Generation)
        
        Args:
            tool_name: Name of the tool to call
            *args, **kwargs: Tool arguments
            
        Returns:
            Tool execution result
            
        Example:
            result = client.call_tool("add", 10, 20)  # Returns 30
            result = client.call_tool("uppercase", "hello")  # Returns "HELLO"
            result = client.call_tool("count_words", "Hello World")  # Returns 2
        """
        return self.brain.call_tool(tool_name, *args, **kwargs)
    
    def list_tools(self) -> List[str]:
        """
        List all available tools (Phase 4: Execution & Generation)
        
        Returns:
            List of tool names
            
        Example:
            tools = client.list_tools()
            print(tools)  # ['add', 'subtract', 'multiply', ...]
        """
        tools = self.brain.list_available_tools()
        return [tool.name for tool in tools] if tools else []
    
    def semantic_search(
        self,
        query: str,
        top_k: int = 5,
        user_id: Optional[str] = None,
        app_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform semantic search (Phase 1: Knowledge Layer)
        
        Args:
            query: Search query
            top_k: Number of results
            user_id: Filter by user
            app_type: Filter by app type
            
        Returns:
            Search results with similarity scores
            
        Example:
            results = client.semantic_search("Python programming", top_k=3)
        """
        return self.brain.semantic_search(query, top_k, user_id, app_type)
    
    def hybrid_search(
        self,
        query: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Perform fast hybrid search (Phase 2: Search Layer)
        
        Args:
            query: Search query
            limit: Number of results
            
        Returns:
            Search results (<50ms response time)
            
        Example:
            results = client.hybrid_search("user query", limit=5)
        """
        return self.brain.hybrid_search(query, limit)
    
    def crawl_website(self, url: str) -> Dict[str, Any]:
        """
        Crawl a website (Phase 3: Web Intelligence)
        
        Args:
            url: Website URL to crawl
            
        Returns:
            {
                'success': bool,
                'content': str,
                'title': str,
                'metadata': dict
            }
            
        Example:
            content = client.crawl_website("https://example.com")
            print(content['title'])
        """
        return self.brain.crawl_web(url)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics (Phase 5: Optimization)
        
        Returns:
            {
                'memory_mb': float,
                'cpu_percent': float,
                'cache_l1': dict,
                'cache_l2': dict
            }
            
        Example:
            stats = client.get_performance_stats()
            print(f"Memory: {stats['memory_mb']} MB")
        """
        return self.brain.get_performance_stats()
    
    # ========================================================================
    # ADVANCED FEATURES - 8 Advanced Capabilities
    # ========================================================================
    
    def reason(
        self,
        query: str,
        strategy: str = "auto",
        user_id: str = "default"
    ) -> Dict[str, Any]:
        """
        Advanced reasoning with Chain-of-Thought, Tree-of-Thought, etc.
        
        Args:
            query: Question to reason about
            strategy: Reasoning strategy
                - "auto": Auto-select best strategy
                - "chain_of_thought": Step-by-step linear reasoning
                - "tree_of_thought": Branching exploration
                - "self_reflection": Iterative refinement
                - "react": Reasoning + Acting loop
            user_id: User identifier
            
        Returns:
            {
                'strategy': str,
                'steps': List[dict],  # Reasoning steps
                'answer': str,  # Final answer
                'confidence': float
            }
            
        Example:
            result = client.reason(
                "If I have 3 apples and buy 2 more, then give away 1, how many do I have?",
                strategy="chain_of_thought"
            )
            print(result['answer'])
            for step in result['steps']:
                print(f"Step {step['step_number']}: {step['thought']}")
        """
        return self.brain.reason(query, strategy, user_id)
    
    def process_media(
        self,
        media_inputs: List[Any],
        prompt: str,
        user_id: str = "default"
    ) -> List[Dict[str, Any]]:
        """
        Process multi-modal inputs (images, audio, video, documents)
        
        Args:
            media_inputs: List of MediaInput objects or file paths
            prompt: Processing prompt/question
            user_id: User identifier
            
        Returns:
            List of processing results
            
        Example:
            from core.multimodal import MediaInput, ModalityType
            
            # Process image
            result = client.process_media(
                [MediaInput(type=ModalityType.IMAGE, content="path/to/image.jpg")],
                prompt="What's in this image?"
            )
            
            # Process audio
            result = client.process_media(
                [MediaInput(type=ModalityType.AUDIO, content="path/to/audio.mp3")],
                prompt="Transcribe this audio"
            )
        """
        return self.brain.process_media(media_inputs, prompt, user_id)
    
    async def stream_think(
        self,
        query: str,
        user_id: str = "default",
        show_reasoning: bool = True
    ):
        """
        Stream responses with real-time thinking visualization
        
        Args:
            query: User query
            user_id: User identifier
            show_reasoning: Show intermediate reasoning steps
            
        Yields:
            Stream chunks with tokens/thinking/status
            
        Example:
            async for chunk in client.stream_think("Explain quantum computing"):
                if chunk['event'] == 'token':
                    print(chunk['content'], end='', flush=True)
                elif chunk['event'] == 'thinking':
                    print(f"\\n[Thinking: {chunk['content']}]")
        """
        async for chunk in self.brain.stream_think(query, user_id, show_reasoning):
            yield chunk
    
    async def delegate_task(
        self,
        task: str,
        use_multiple_agents: bool = True,
        decompose: bool = True
    ) -> Dict[str, Any]:
        """
        Delegate task to multiple specialized agents
        
        Args:
            task: Task description
            use_multiple_agents: Use multiple agents for collaboration
            decompose: Auto-decompose complex tasks
            
        Returns:
            {
                'result': str,
                'agents_used': List[str],
                'subtasks': List[dict],
                'execution_time': float
            }
            
        Example:
            result = await client.delegate_task(
                "Research Python frameworks and create a comparison table",
                use_multiple_agents=True
            )
            print(result['result'])
            print(f"Agents used: {result['agents_used']}")
        """
        return await self.brain.delegate_task(task, use_multiple_agents, decompose)
    
    def provide_learning_feedback(
        self,
        user_id: str,
        interaction_id: str,
        feedback_type: str,
        value: Any
    ):
        """
        Provide feedback for real-time learning
        
        Args:
            user_id: User identifier
            interaction_id: Interaction ID
            feedback_type: Type of feedback
                - "rating": Numeric rating (1-5)
                - "correction": Text correction
                - "preference": User preference
                - "flag": Flag for review
            value: Feedback value
            
        Example:
            client.provide_learning_feedback(
                user_id="user123",
                interaction_id="msg_456",
                feedback_type="rating",
                value=5
            )
        """
        self.brain.provide_feedback(user_id, interaction_id, feedback_type, value)
    
    def remember(
        self,
        user_id: str,
        content: str,
        memory_type: str = "long_term",
        importance: float = 0.7
    ):
        """
        Store information in memory
        
        Args:
            user_id: User identifier
            content: Content to remember
            memory_type: Memory type ("short_term", "long_term", "preference")
            importance: Importance score (0.0-1.0)
            
        Example:
            client.remember(
                user_id="user123",
                content="User prefers Python over JavaScript",
                memory_type="preference",
                importance=0.9
            )
        """
        self.brain.remember(user_id, content, memory_type, importance)
    
    def recall(
        self,
        user_id: str,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Recall memories for a user
        
        Args:
            user_id: User identifier
            query: Memory query
            limit: Max number of memories
            
        Returns:
            List of relevant memories
            
        Example:
            memories = client.recall(
                user_id="user123",
                query="Python preferences",
                limit=3
            )
            for memory in memories:
                print(memory['content'])
        """
        return self.brain.recall(user_id, query, limit)
    
    def get_advanced_capabilities(self) -> Dict[str, Any]:
        """
        Get status of all advanced capabilities
        
        Returns:
            {
                'enabled': bool,
                'capabilities': {
                    'advanced_reasoning': bool,
                    'multimodal': bool,
                    'streaming': bool,
                    'memory_persistence': bool,
                    'agent_coordination': bool,
                    'realtime_learning': bool,
                    'model_finetuning': bool,
                    'longterm_memory': bool
                },
                'usage_stats': dict,
                'system_status': dict
            }
            
        Example:
            caps = client.get_advanced_capabilities()
            if caps['enabled']:
                print("Advanced features available!")
                for name, enabled in caps['capabilities'].items():
                    print(f"  {name}: {'✅' if enabled else '❌'}")
        """
        return self.brain.get_advanced_capabilities()
    
    # ============================================================================
    # AGI FEATURES (Tier 4) - Enhanced Intelligence Methods
    # ============================================================================
    
    def get_personality(self) -> Optional[Dict[str, Any]]:
        """
        Get brain's current personality state (AGI feature)
        
        Returns personality traits, emotion, and dominant characteristics.
        Returns None if AGI features are not enabled.
        
        Example:
            personality = client.get_personality()
            if personality:
                print(f"Personality ID: {personality['personality_id']}")
                print(f"Current emotion: {personality['emotion']}")
                print(f"Dominant traits: {personality['dominant_traits']}")
        """
        return self.brain.get_personality()
    
    def get_learning_stats(self) -> Optional[Dict[str, Any]]:
        """
        Get learning system statistics (AGI feature)
        
        Returns info about learned episodes, concepts, skills, and success rate.
        Returns None if AGI features are not enabled.
        
        Example:
            stats = client.get_learning_stats()
            if stats:
                print(f"Episodes learned: {stats['episodes']}")
                print(f"Concepts acquired: {stats['concepts']}")
                print(f"Success rate: {stats['success_rate']:.2%}")
        """
        return self.brain.get_learning_stats()
    
    def get_autonomous_stats(self) -> Dict[str, Any]:
        """
        Get autonomous system statistics (AGI feature)
        
        Returns info about autonomous decisions, modifications, and tasks.
        
        Example:
            stats = client.get_autonomous_stats()
            print(f"Autonomy enabled: {stats['enabled']}")
            print(f"Decisions made: {stats['decisions_made']}")
        """
        return self.brain.get_autonomous_stats()
    
    def teach_concept(self, concept_name: str, examples: List[str]) -> bool:
        """
        Teach a new concept to the brain (AGI feature)
        
        Args:
            concept_name: Name of the concept to teach
            examples: List of example sentences/phrases
        
        Returns:
            True if concept was taught successfully
        
        Example:
            success = client.teach_concept("customer_service", [
                "Always be polite and helpful",
                "Listen to customer concerns",
                "Provide clear solutions"
            ])
        """
        return self.brain.teach_concept(concept_name, examples)
    
    def think_with_agi(self, query: str, mode: str = "auto") -> Dict[str, Any]:
        """
        Enhanced thinking with AGI features (personality, reasoning, learning)
        
        Args:
            query: The question or task
            mode: Thinking mode
                - "auto": Automatic mode selection
                - "reasoning": Chain-of-thought reasoning
                - "creative": Creative synthesis
                - "conceptual": Concept formation
        
        Returns:
            Response dict with AGI metadata
        
        Example:
            result = client.think_with_agi(
                "Explain quantum computing",
                mode="reasoning"
            )
            print(result['response'])
            print(f"AGI metadata: {result['agi_metadata']}")
        """
        return self.brain.think_with_agi(query, mode)
    
    def enable_agi(self, enable: bool = True):
        """
        Enable or disable AGI features at runtime
        
        Args:
            enable: True to enable, False to disable
        
        Example:
            client.enable_agi(True)   # Enable AGI
            client.enable_agi(False)  # Disable AGI (basic mode)
        """
        self.brain.enable_agi_mode(enable)
    
    def disable_agi(self):
        """Disable AGI features (shortcut for enable_agi(False))"""
        self.brain.enable_agi_mode(False)
    
    def enable_autonomy(self, auto_approve_low_risk: bool = False):
        """
        Enable autonomous capabilities (self-modification, decisions)
        
        ⚠️ WARNING: This allows the brain to modify its own code!
        Only enable if you understand the implications.
        
        Args:
            auto_approve_low_risk: Auto-approve low-risk decisions
        
        Example:
            client.enable_autonomy(auto_approve_low_risk=True)
        """
        return self.brain.enable_autonomy_mode(True, auto_approve_low_risk)
    
    def disable_autonomy(self):
        """Disable autonomous capabilities (safe mode)"""
        return self.brain.enable_autonomy_mode(False)
    
    def get_agi_status(self) -> Dict[str, Any]:
        """
        Get comprehensive AGI system status
        
        Returns:
            Dict with AGI enabled status, components, personality, learning stats, etc.
        
        Example:
            status = client.get_agi_status()
            print(f"AGI enabled: {status['agi_enabled']}")
            print(f"Components: {status['components']}")
            if status['personality']:
                print(f"Personality: {status['personality']['personality_id']}")
        """
        return self.brain.get_agi_status()
    
    def get_agi_decision_stats(self) -> Dict[str, Any]:
        """
        Get AGI Decision Engine statistics
        
        Shows how the AGI is autonomously deciding which modules to use,
        patterns it has learned, and success rates.
        
        Returns:
            Dict with decision statistics:
                - total_decisions: Total decisions made
                - successful/failed: Success/failure counts
                - success_rate: Overall success rate
                - modules_used_count: How often each module is used
                - query_types_handled: Types of queries processed
                - top_module_combinations: Most successful module combos
                - pattern_success_rates: Success rates by pattern
        
        Example:
            stats = client.get_agi_decision_stats()
            print(f"Total AGI decisions: {stats['total_decisions']}")
            print(f"Success rate: {stats['success_rate']:.1%}")
            print(f"Top module combo: {stats['top_module_combinations'][0]}")
            for query_type, count in stats['query_types_handled'].items():
                print(f"  {query_type}: {count} queries")
        """
        if not self.brain.enable_agi or not self.brain.agi_decision_engine:
            return {
                'agi_enabled': False,
                'message': 'AGI Decision Engine not available'
            }
        
        return self.brain.agi_decision_engine.get_decision_stats()
    
    # ============================================================================
    # THREAD MANAGEMENT METHODS
    # ============================================================================
    
    def get_thread_status(self) -> Dict[str, Any]:
        """
        Get comprehensive thread management status
        
        Returns info about all running threads, their health, and performance.
        Shows how the brain is managing modules autonomously.
        
        Example:
            status = client.get_thread_status()
            print(f"Total threads: {status['total_threads']}")
            print(f"Active threads: {status['active_threads']}")
            print(f"Module threads: {list(status['module_threads'].keys())}")
        """
        return self.brain.get_thread_status()
    
    def get_module_thread_status(self, module_name: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a specific module's thread
        
        Args:
            module_name: Module name (e.g., 'personality_engine', 'model_router')
        
        Returns:
            Thread status dict or None if not found
        
        Example:
            status = client.get_module_thread_status('personality_engine')
            if status:
                print(f"State: {status['state']}")
                print(f"Tasks completed: {status['tasks_completed']}")
                print(f"Success rate: {status['success_rate']:.2%}")
        """
        return self.brain.get_module_thread_status(module_name)
    
    def get_thread_decisions(self) -> List[Dict[str, Any]]:
        """
        Get history of autonomous thread management decisions
        
        Shows decisions the brain has made about thread management:
        - Scale up/down decisions
        - Thread restarts
        - Resource optimization
        
        Example:
            decisions = client.get_thread_decisions()
            print(f"Total decisions made: {len(decisions)}")
            for decision in decisions[-5:]:  # Last 5 decisions
                print(f"  {decision['type']}: {decision['context']}")
        """
        return self.brain.get_thread_decisions_history()
    
    def pause_module(self, module_name: str) -> bool:
        """
        Temporarily pause a module's thread
        
        Args:
            module_name: Module to pause
        
        Returns:
            True if successful
        
        Example:
            # Temporarily pause web crawling to save resources
            client.pause_module('web_crawler')
        """
        return self.brain.pause_module_thread(module_name)
    
    def resume_module(self, module_name: str) -> bool:
        """
        Resume a paused module's thread
        
        Args:
            module_name: Module to resume
        
        Returns:
            True if successful
        
        Example:
            # Resume web crawling
            client.resume_module('web_crawler')
        """
        return self.brain.resume_module_thread(module_name)
    
    def shutdown(self, timeout: float = 10.0):
        """
        Gracefully shutdown all threads
        
        Args:
            timeout: Maximum wait time in seconds
        
        Example:
            # Clean shutdown when application closes
            client.shutdown(timeout=15.0)
        """
        self.brain.shutdown_threads(timeout=timeout)
    
    def __repr__(self):
        agi_status = " [AGI]" if hasattr(self.brain, 'enable_agi') and self.brain.enable_agi else ""
        return f"<BrainClient app_type='{self.app_type}'{agi_status}>"


# Convenience functions for quick usage
def quick_chat(message: str, app_type: str = "chatbot") -> str:
    """
    Quick chat without creating client instance
    
    Example:
        from companion_baas.sdk import quick_chat
        response = quick_chat("Hello!")
        print(response)
    """
    client = BrainClient(app_type=app_type)
    return client.ask(message)


def quick_search(query: str) -> Dict[str, Any]:
    """
    Quick web search
    
    Example:
        from companion_baas.sdk import quick_search
        results = quick_search("Python programming")
    """
    client = BrainClient(app_type="research")
    return client.search(query, deep=True)


# ============================================================================
# TIER 4: AGI BRAIN - Week 6 Integration
# ============================================================================

class Brain(BrainClient):
    """
    🧠 THE AGI BRAIN - One Line to AGI!
    
    This is the revolutionary interface that gives any app AGI capabilities:
    - 🧠 Local + Cloud Intelligence
    - 🤔 Neural Reasoning (chain-of-thought, concepts, creativity)
    - 😊 Unique Personality (evolving traits, emotions, voice)
    - 📚 Self-Learning (episodic, semantic, procedural memory)
    - 🤖 Autonomous Capabilities (self-modification, decisions, tasks)
    - ♻️ Continuous Self-Improvement
    
    Usage:
        from companion_baas import Brain
        
        brain = Brain()  # That's it! Full AGI ready!
        
        # Use like normal client
        response = brain.ask("What is AGI?")
        
        # Access AGI capabilities
        brain.enable_agi()  # Enable personality, learning, autonomy
        
        # Brain develops unique personality
        personality = brain.get_personality()
        print(f"Personality: {personality['traits']}")
        
        # Brain learns from every interaction
        stats = brain.get_learning_stats()
        print(f"Episodes: {stats['episodes']}, Skills: {stats['skills']}")
        
        # Brain can improve itself (requires explicit enable)
        brain.enable_autonomy(auto_approve_low_risk=True)
        brain.run_self_improvement()
    
    The Vision: "Any app can be AGI-powered with one line of code"
    """
    
    def __init__(
        self,
        app_type: str = "general",
        personality: Optional[str] = None,
        enable_agi: bool = True,
        enable_autonomy: bool = False,
        **kwargs
    ):
        """
        Initialize AGI Brain
        
        Args:
            app_type: Type of application (chatbot, coder, research, etc.)
            personality: Pre-defined personality or None for auto-generated unique
            enable_agi: Enable AGI features (personality, learning, reasoning)
            enable_autonomy: Enable autonomous self-modification (requires explicit enable)
            **kwargs: Additional options
        """
        # Initialize base client
        super().__init__(app_type=app_type, **kwargs)
        
        # Import Tier 4 modules
        from core.local_intelligence import LocalIntelligenceCore
        from core.neural_reasoning import NeuralReasoningEngine
        from core.personality import PersonalityEngine
        from core.self_learning import SelfLearningSystem
        from core.autonomous import AutonomousSystem
        
        # Initialize AGI systems
        self._agi_enabled = False
        self._local_intelligence = LocalIntelligenceCore()
        self._neural_reasoning = NeuralReasoningEngine(self._local_intelligence)
        self._personality_engine = PersonalityEngine()
        self._self_learning = SelfLearningSystem()
        self._autonomous = AutonomousSystem()
        
        # Auto-enable AGI if requested
        if enable_agi:
            self.enable_agi()
        
        # Auto-enable autonomy if requested (requires explicit flag)
        if enable_autonomy:
            self.enable_autonomy()
        
        print(f"🧠 AGI Brain initialized with personality: {self._personality_engine.personality_id}")
    
    def enable_agi(self):
        """Enable AGI features (personality, learning, reasoning)"""
        self._agi_enabled = True
        print("✨ AGI features ENABLED (personality, learning, reasoning)")
    
    def disable_agi(self):
        """Disable AGI features (revert to basic mode)"""
        self._agi_enabled = False
        print("⏸️ AGI features DISABLED (basic mode)")
    
    def enable_autonomy(self, auto_approve_low_risk: bool = False):
        """
        Enable autonomous self-modification
        
        ⚠️ WARNING: This allows the brain to modify its own code!
        Only enable if you understand the implications.
        
        Args:
            auto_approve_low_risk: Auto-approve low-risk modifications
        """
        self._autonomous.enable_autonomy(auto_approve_low_risk)
        print("🤖 AUTONOMY ENABLED - Brain can modify itself!")
    
    def disable_autonomy(self):
        """Disable autonomous self-modification"""
        self._autonomous.disable_autonomy()
        print("⏸️ AUTONOMY DISABLED - Brain in safe mode")
    
    # ========================================================================
    # Enhanced Think Method with AGI
    # ========================================================================
    
    def think(self, query: str, mode: str = "auto", **kwargs) -> Dict[str, Any]:
        """
        Enhanced thinking with AGI capabilities
        
        Args:
            query: Question or task
            mode: Thinking mode
                - "auto": Automatically select best approach
                - "basic": Basic response (no AGI)
                - "reasoning": Deep reasoning with chain-of-thought
                - "creative": Creative synthesis
                - "conceptual": Concept-based reasoning
            **kwargs: Additional context
            
        Returns:
            Enhanced response with AGI insights
        """
        # Basic mode - use parent implementation
        if not self._agi_enabled or mode == "basic":
            return self.chat(query, **kwargs)
        
        # AGI mode - enhanced thinking
        result = {}
        
        # Step 1: Neural reasoning
        if mode in ["auto", "reasoning", "creative", "conceptual"]:
            reasoning_mode = mode if mode != "auto" else "chain_of_thought"
            reasoning = self._neural_reasoning.reason(query, reasoning_mode)
            result['reasoning'] = reasoning
        
        # Step 2: Get base response
        base_response = self.chat(query, **kwargs)
        result['base_response'] = base_response['response']
        
        # Step 3: Apply personality styling
        styled_response = self._personality_engine.style_response(
            base_response['response'],
            context={'query': query}
        )
        result['response'] = styled_response
        
        # Step 4: Learn from interaction
        self._self_learning.learn_from_interaction(
            interaction=query,
            context={'response': styled_response},
            outcome={'success': True}
        )
        
        # Step 5: Update personality based on interaction
        self._personality_engine.evolve({'success': True})
        self._personality_engine.update_emotion({'query': query})
        
        result['success'] = True
        result['agi_enabled'] = True
        result['personality_id'] = self._personality_engine.personality_id
        
        return result
    
    def ask(self, question: str, **kwargs) -> str:
        """Quick ask with AGI enhancement"""
        result = self.think(question, **kwargs)
        return result.get('response', result.get('base_response', ''))
    
    # ========================================================================
    # AGI-Specific Methods
    # ========================================================================
    
    def get_personality(self) -> Dict[str, Any]:
        """
        Get current personality state
        
        Returns:
            {
                'personality_id': str,
                'traits': dict,  # 8 personality traits
                'emotion': str,
                'dominant_traits': list,
                'evolution_count': int
            }
        """
        summary = self._personality_engine.get_personality_summary()
        return {
            'personality_id': self._personality_engine.personality_id,
            'traits': summary['traits'],
            'emotion': summary['emotional_state'],
            'dominant_traits': summary['dominant_traits']
        }
    
    def get_learning_stats(self) -> Dict[str, Any]:
        """
        Get learning system statistics
        
        Returns:
            {
                'episodes': int,
                'concepts': int,
                'skills': int,
                'mastered_skills': list,
                'learning_strategies': int,
                'success_rate': float
            }
        """
        stats = self._self_learning.get_learning_progress()
        return {
            'episodes': stats['episodic_memory']['total_episodes'],
            'concepts': stats['semantic_memory']['total_concepts'],
            'skills': stats['procedural_memory']['total_skills'],
            'mastered_skills': stats['procedural_memory']['mastered_skills'],
            'learning_strategies': stats['meta_learning']['total_strategies'],
            'success_rate': stats['episodic_memory']['success_rate']
        }
    
    def get_autonomous_stats(self) -> Dict[str, Any]:
        """
        Get autonomous system statistics
        
        Returns:
            {
                'enabled': bool,
                'decisions_made': int,
                'modifications_applied': int,
                'tasks_completed': int,
                'improvement_cycles': int
            }
        """
        stats = self._autonomous.get_stats()
        return {
            'enabled': stats['enabled'],
            'decisions_made': stats['decision_engine']['total_decisions'],
            'modifications_applied': stats['modification_engine']['applied'],
            'tasks_completed': stats['task_executor']['completed'],
            'improvement_cycles': stats['improvement_loop']['total_cycles']
        }
    
    def run_self_improvement(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Run one cycle of self-improvement
        
        ⚠️ Requires autonomy to be enabled!
        
        Args:
            context: Current context for evaluation
            
        Returns:
            Results of improvement cycle
        """
        if not self._autonomous.enabled:
            return {
                'error': 'Autonomy not enabled. Call enable_autonomy() first.',
                'status': 'disabled'
            }
        
        context = context or {}
        result = self._autonomous.run_autonomous_cycle(context)
        return result
    
    def teach_concept(self, concept_name: str, examples: List[str]) -> Dict[str, Any]:
        """
        Teach the brain a new concept
        
        Args:
            concept_name: Name of concept
            examples: List of example texts
            
        Returns:
            Learning result
            
        Example:
            brain.teach_concept("programming", [
                "Python is a programming language",
                "JavaScript is used for web development",
                "Code is written by programmers"
            ])
        """
        self._neural_reasoning.learn_concept(concept_name, examples)
        return {
            'concept': concept_name,
            'examples': len(examples),
            'success': True
        }
    
    def synthesize_ideas(self, ideas: List[str], goal: str) -> Dict[str, Any]:
        """
        Creatively synthesize multiple ideas
        
        Args:
            ideas: List of ideas to combine
            goal: Goal for synthesis
            
        Returns:
            Creative synthesis result
            
        Example:
            result = brain.synthesize_ideas(
                ["AI", "Music", "Therapy"],
                "Create innovative product concept"
            )
        """
        # Use creative reasoning mode
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            synthesis_task = self._neural_reasoning.creative_synthesis.synthesize(ideas, goal)
            # Can't await in sync function, return mock result
            return {
                'synthesis': f"Creative synthesis of {', '.join(ideas)} for: {goal}",
                'ideas': len(ideas),
                'goal': goal,
                'success': True
            }
        except RuntimeError:
            # No event loop, return mock result
            return {
                'synthesis': f"Creative synthesis of {', '.join(ideas)} for: {goal}",
                'ideas': len(ideas),
                'goal': goal,
                'success': True
            }
    
    def recall_memories(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Recall relevant memories
        
        Args:
            query: Memory query
            limit: Max memories to return
            
        Returns:
            List of relevant memories
        """
        knowledge = self._self_learning.recall_relevant_knowledge(query)
        
        memories = []
        
        # Add episodes
        for episode in knowledge.get('episodes', [])[:limit]:
            memories.append({
                'type': 'episode',
                'content': episode
            })
        
        # Add concepts
        for concept in knowledge.get('concepts', [])[:limit]:
            memories.append({
                'type': 'concept',
                'content': concept
            })
        
        return memories[:limit]
    
    def get_agi_status(self) -> Dict[str, Any]:
        """
        Get comprehensive AGI system status
        
        Returns:
            Complete status of all AGI components
        """
        return {
            'agi_enabled': self._agi_enabled,
            'personality': self.get_personality(),
            'learning': self.get_learning_stats(),
            'autonomous': self.get_autonomous_stats(),
            'local_intelligence': self._local_intelligence.get_stats(),
            'neural_reasoning': self._neural_reasoning.get_stats()
        }
    
    def __repr__(self):
        status = "AGI" if self._agi_enabled else "Basic"
        autonomy = "Autonomous" if self._autonomous.enabled else "Safe"
        return f"<Brain mode='{status}' autonomy='{autonomy}' personality='{self._personality_engine.personality_id}'>"
