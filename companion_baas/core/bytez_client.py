"""
Bytez API Client for Companion Brain
Provides access to 141k+ small models (0-10B params) with unlimited tokens
"""

import logging
from typing import List, Dict, Optional, Any

try:
    from bytez import Bytez
    BYTEZ_AVAILABLE = True
except ImportError:
    BYTEZ_AVAILABLE = False

logger = logging.getLogger(__name__)


class BytezClient:
    """
    Client for Bytez API - Access to 141k+ small models
    Free tier: 0-10B params, unlimited tokens, 1 concurrent request
    """
    
    # Popular models on Bytez platform (with proper chat templates)
    RECOMMENDED_MODELS = {
        'chat': 'Qwen/Qwen2.5-3B-Instruct',  # Fast chat model with chat template
        'code': 'Qwen/Qwen2.5-Coder-3B-Instruct',  # Code generation
        'reasoning': 'Qwen/Qwen2.5-3B-Instruct',  # Reasoning tasks
        'general': 'Qwen/Qwen2.5-3B-Instruct',  # Reliable model
        'multilingual': 'Qwen/Qwen2.5-3B-Instruct',  # Multi-purpose
    }
    
    # Model name aliases - map short names to full model IDs
    # Using models that have proper chat templates configured
    MODEL_ALIASES = {
        'qwen-4b': 'Qwen/Qwen2.5-3B-Instruct',  # Qwen with proper chat template
        'phi-2-reasoner': 'Qwen/Qwen2.5-3B-Instruct',  # Fallback to working model
        'phi-2': 'Qwen/Qwen2.5-3B-Instruct',  # Fallback to working model
        'deepseek-coder': 'deepseek-ai/deepseek-coder-1.3b-instruct',
        'tinyllama': 'TinyLlama/TinyLlama-1.1B-Chat-v1.0',
        'qwen-32b': 'Qwen/Qwen2.5-3B-Instruct',  # All map to same working model
        'qwen-72b': 'Qwen/Qwen2.5-3B-Instruct',
        'qwen-math': 'Qwen/Qwen2.5-3B-Instruct',
    }
    
    def __init__(self, api_key: str):
        """
        Initialize Bytez client
        
        Args:
            api_key: Bytez API key
        """
        if not BYTEZ_AVAILABLE:
            logger.warning("⚠️  Bytez library not installed. Run: pip install bytez")
            self.client = None
            self.enabled = False
            return
        
        if not api_key:
            logger.warning("⚠️  Bytez API key not provided")
            self.client = None
            self.enabled = False
            return
        
        try:
            self.client = Bytez(api_key)
            self.api_key = api_key
            self.enabled = True
            logger.info("✅ Bytez client initialized - 141k+ models available!")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Bytez client: {e}")
            self.client = None
            self.enabled = False
    
    def generate(self,
                messages: List[Dict[str, str]],
                model: Optional[str] = None,
                task_type: str = 'chat',
                max_tokens: Optional[int] = None,
                temperature: float = 0.7,
                **kwargs) -> Dict[str, Any]:
        """
        Generate response using Bytez model
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model ID (if None, uses recommended model for task_type)
            task_type: Type of task ('chat', 'code', 'reasoning', 'general')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional parameters
            
        Returns:
            Dict with 'response', 'model', 'error', etc.
        """
        if not self.enabled:
            return {
                'success': False,
                'error': 'Bytez client not available',
                'response': None
            }
        
        try:
            # Select model
            if not model:
                model = self.RECOMMENDED_MODELS.get(task_type, self.RECOMMENDED_MODELS['chat'])
            
            # Resolve model aliases
            model = self.MODEL_ALIASES.get(model, model)
            
            logger.info(f"🤖 Bytez request to {model}")
            
            # Get model instance
            model_instance = self.client.model(model)
            
            # Run inference
            try:
                result = model_instance.run(messages)
            except Exception as run_error:
                logger.error(f"❌ Bytez model.run() failed: {run_error}")
                return {
                    'success': False,
                    'error': f"Model execution failed: {str(run_error)}",
                    'response': None,
                    'model': model
                }
            
            # Check if result is None or invalid
            if result is None:
                logger.error(f"❌ Bytez returned None for model {model}")
                return {
                    'success': False,
                    'error': f"Model {model} returned no response (may not exist)",
                    'response': None,
                    'model': model
                }
            
            # Check for errors
            if hasattr(result, 'error') and result.error:
                logger.error(f"❌ Bytez error: {result.error}")
                return {
                    'success': False,
                    'error': str(result.error),
                    'response': None,
                    'model': model
                }
            
            # Extract response text
            if hasattr(result, 'output'):
                output = result.output
            else:
                output = result
            
            response_text = self._extract_response(output)
            
            logger.info(f"✅ Bytez response: {len(response_text)} chars")
            
            return {
                'success': True,
                'response': response_text,
                'model': model,
                'provider': 'bytez',
                'error': None,
                'metadata': {
                    'raw_output': output,
                    'task_type': task_type
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Bytez generation failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'response': None,
                'model': model
            }
    
    def _extract_response(self, output: Any) -> str:
        """Extract text response from Bytez output"""
        if isinstance(output, str):
            return output
        elif isinstance(output, dict):
            # Try common response keys
            for key in ['content', 'text', 'response', 'message', 'output']:
                if key in output:
                    return str(output[key])
            # Return first string value found
            for value in output.values():
                if isinstance(value, str):
                    return value
            return str(output)
        elif isinstance(output, list) and len(output) > 0:
            return self._extract_response(output[0])
        else:
            return str(output)
    
    def chat(self,
            prompt: str,
            model: Optional[str] = None,
            system_prompt: Optional[str] = None,
            **kwargs) -> str:
        """
        Simple chat interface
        
        Args:
            prompt: User prompt
            model: Model ID (optional)
            system_prompt: System prompt (optional)
            **kwargs: Additional parameters
            
        Returns:
            Response text
        """
        messages = []
        
        if system_prompt:
            messages.append({
                'role': 'system',
                'content': system_prompt
            })
        
        messages.append({
            'role': 'user',
            'content': prompt
        })
        
        result = self.generate(messages, model=model, **kwargs)
        
        if result['success']:
            return result['response']
        else:
            raise Exception(f"Bytez error: {result['error']}")
    
    def list_recommended_models(self) -> Dict[str, str]:
        """Get dictionary of recommended models by task type"""
        return self.RECOMMENDED_MODELS.copy()
    
    def is_enabled(self) -> bool:
        """Check if Bytez client is available"""
        return self.enabled


# Singleton instance
_bytez_client: Optional[BytezClient] = None


def get_bytez_client(api_key: Optional[str] = None) -> BytezClient:
    """
    Get global Bytez client instance
    
    Args:
        api_key: Bytez API key (only needed on first call)
        
    Returns:
        BytezClient instance
    """
    global _bytez_client
    
    if _bytez_client is None:
        if api_key is None:
            import os
            api_key = os.getenv('BYTEZ_API_KEY')
        
        _bytez_client = BytezClient(api_key)
    
    return _bytez_client


# Quick functions
def bytez_chat(prompt: str, model: Optional[str] = None, api_key: Optional[str] = None) -> str:
    """Quick chat function"""
    client = get_bytez_client(api_key)
    return client.chat(prompt, model=model)


def bytez_generate(messages: List[Dict], model: Optional[str] = None, api_key: Optional[str] = None) -> Dict:
    """Quick generate function"""
    client = get_bytez_client(api_key)
    return client.generate(messages, model=model)
