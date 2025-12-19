#!/usr/bin/env python3
"""
Neural Brain Integration Layer
===============================

Integrates the neural brain with existing Companion infrastructure
"""

import sys
import os
import logging
from typing import Dict, Any, Optional, List
import asyncio

# Add parent directories to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, os.path.join(parent_dir, '..', 'website'))

from neural_brain import NeuralCompanionBrain, NeuralBrainClient, ReasoningStrategy

# Import existing Companion components
try:
    from api_wrapper import generate_companion_response
    from search_engine_wrapper import search_wrapper
    from response_cache import response_cache
except ImportError:
    # Fallback if imports fail
    generate_companion_response = None
    search_wrapper = None
    response_cache = None

logger = logging.getLogger(__name__)


class HybridBrain:
    """
    Hybrid Brain that combines Neural Network intelligence with existing LLM APIs
    
    This provides the best of both worlds:
    - Neural network for intelligence, reasoning, memory
    - LLM APIs for actual text generation
    """
    
    def __init__(
        self,
        app_type: str = "general",
        use_neural: bool = True,
        enable_distribution: bool = False
    ):
        self.app_type = app_type
        self.use_neural = use_neural
        
        # Initialize neural brain
        if use_neural:
            try:
                self.neural_brain = NeuralCompanionBrain(
                    app_type=app_type,
                    enable_distribution=enable_distribution
                )
                logger.info("✅ Neural brain initialized")
            except Exception as e:
                logger.warning(f"⚠️ Neural brain initialization failed: {e}")
                logger.warning("   Falling back to standard mode")
                self.neural_brain = None
                self.use_neural = False
        else:
            self.neural_brain = None
        
        self.stats = {
            'neural_requests': 0,
            'standard_requests': 0,
            'hybrid_requests': 0
        }
    
    async def think(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        tools: Optional[List[str]] = None,
        conversation_id: Optional[str] = None,
        use_reasoning: bool = True,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Hybrid thinking that uses both neural intelligence and LLM generation
        
        Flow:
        1. Neural brain analyzes intent, extracts entities, retrieves memories
        2. Neural brain performs reasoning if needed
        3. LLM generates actual response using neural insights
        4. Neural brain reflects on response quality
        5. Store in neural memory for future use
        """
        
        if not self.use_neural or self.neural_brain is None:
            # Fallback to standard generation
            return await self._standard_think(message, context, tools, conversation_id)
        
        try:
            self.stats['hybrid_requests'] += 1
            
            # Step 1: Neural analysis
            logger.info("🧠 Neural analysis...")
            neural_result = await self.neural_brain.think(
                message=message,
                context=context,
                reasoning_strategy=ReasoningStrategy.CHAIN_OF_THOUGHT if use_reasoning else ReasoningStrategy.DIRECT,
                stream=False
            )
            
            if not neural_result['success']:
                logger.warning("⚠️ Neural analysis failed, using standard mode")
                return await self._standard_think(message, context, tools, conversation_id)
            
            # Extract neural insights
            intent = neural_result['metadata']['intent']
            entities = neural_result['metadata']['entities']
            reasoning = neural_result['metadata'].get('reasoning')
            quality = neural_result['metadata']['quality']
            
            logger.info(f"   Intent: {intent['intent']} ({intent['intent_confidence']:.2%})")
            logger.info(f"   Entities: {len(entities)} extracted")
            logger.info(f"   Reasoning: {'Applied' if reasoning else 'Not needed'}")
            
            # Step 2: Prepare enhanced context for LLM
            enhanced_context = {
                **(context or {}),
                'neural_intent': intent,
                'neural_entities': entities,
                'neural_reasoning': reasoning,
                'conversation_id': conversation_id
            }
            
            # Step 3: Generate response using LLM with neural insights
            if generate_companion_response:
                logger.info("💬 Generating LLM response with neural insights...")
                
                # Build enhanced prompt
                enhanced_message = message
                if reasoning:
                    enhanced_message = f"{message}\n\n[Analysis: {reasoning['reasoning_path']}]"
                
                api_response = generate_companion_response(
                    message=enhanced_message,
                    tools=tools or [],
                    chat_history=[]  # Would get from conversation_id
                )
                
                if api_response.success:
                    response_text = api_response.content
                    model_used = api_response.model
                else:
                    response_text = neural_result['response']
                    model_used = "neural_fallback"
            else:
                # Pure neural response
                response_text = neural_result['response']
                model_used = "neural_brain"
            
            # Step 4: Return hybrid result
            return {
                'success': True,
                'response': response_text,
                'metadata': {
                    'mode': 'hybrid',
                    'model': model_used,
                    'neural_analysis': {
                        'intent': intent,
                        'entities': entities,
                        'reasoning': reasoning,
                        'quality_prediction': quality
                    },
                    'response_time': neural_result['metadata']['response_time']
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Hybrid brain error: {e}")
            # Fallback to standard
            return await self._standard_think(message, context, tools, conversation_id)
    
    async def _standard_think(
        self,
        message: str,
        context: Optional[Dict[str, Any]],
        tools: Optional[List[str]],
        conversation_id: Optional[str]
    ) -> Dict[str, Any]:
        """Standard thinking without neural brain"""
        self.stats['standard_requests'] += 1
        
        if generate_companion_response:
            api_response = generate_companion_response(
                message=message,
                tools=tools or [],
                chat_history=[]
            )
            
            if api_response.success:
                return {
                    'success': True,
                    'response': api_response.content,
                    'metadata': {
                        'mode': 'standard',
                        'model': api_response.model,
                        'source': api_response.source
                    }
                }
        
        return {
            'success': False,
            'error': 'No generation method available'
        }
    
    async def think_stream(self, message: str) -> Any:
        """Streaming response"""
        if self.neural_brain:
            async for token in self.neural_brain.think_stream(message):
                yield token
        else:
            yield "Streaming not available in standard mode"
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive stats"""
        stats = {**self.stats}
        
        if self.neural_brain:
            stats['neural_brain'] = self.neural_brain.get_stats()
        
        return stats


# ============================================================================
# Flask/FastAPI Integration
# ============================================================================

class BrainMiddleware:
    """
    Middleware for integrating neural brain with web frameworks
    """
    
    def __init__(self, app_type: str = "chatbot"):
        self.brain = HybridBrain(app_type=app_type, use_neural=True)
        logger.info(f"🧠 Brain middleware initialized for {app_type}")
    
    async def process_message(
        self,
        message: str,
        conversation_id: str,
        tools: List[str] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Process incoming message
        
        This is the main entry point for web applications
        """
        return await self.brain.think(
            message=message,
            conversation_id=conversation_id,
            tools=tools,
            stream=stream
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for monitoring"""
        return self.brain.get_stats()


# ============================================================================
# Convenience Functions
# ============================================================================

# Global brain instance (singleton pattern)
_global_brain = None


def get_brain(app_type: str = "general") -> HybridBrain:
    """Get or create global brain instance"""
    global _global_brain
    
    if _global_brain is None:
        _global_brain = HybridBrain(app_type=app_type)
    
    return _global_brain


async def quick_chat(message: str, app_type: str = "chatbot") -> str:
    """
    Quick chat function for simple use cases
    
    Example:
        response = await quick_chat("Hello!")
        print(response)
    """
    brain = get_brain(app_type)
    result = await brain.think(message)
    return result.get('response', 'Error occurred')


# ============================================================================
# Example: Integration with existing chat backend
# ============================================================================

async def integrate_with_chat_backend():
    """
    Example of how to integrate with the existing chat backend
    """
    
    # Initialize brain middleware
    middleware = BrainMiddleware(app_type="chatbot")
    
    # Simulate incoming message (would come from Flask route)
    conversation_id = "test-conversation-123"
    message = "What is the meaning of life?"
    tools = ["web", "think"]
    
    # Process message
    result = await middleware.process_message(
        message=message,
        conversation_id=conversation_id,
        tools=tools
    )
    
    if result['success']:
        print(f"Response: {result['response']}")
        print(f"Mode: {result['metadata']['mode']}")
        
        if 'neural_analysis' in result['metadata']:
            neural = result['metadata']['neural_analysis']
            print(f"Intent: {neural['intent']['intent']}")
            print(f"Quality: {neural['quality_prediction']['overall']:.2%}")
    else:
        print(f"Error: {result.get('error')}")
    
    # Get stats
    stats = middleware.get_stats()
    print(f"\nStats: {stats}")


if __name__ == "__main__":
    # Run integration example
    print("=" * 70)
    print("🧠💫 Neural Brain Integration Demo")
    print("=" * 70)
    
    asyncio.run(integrate_with_chat_backend())
