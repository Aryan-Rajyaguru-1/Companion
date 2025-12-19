#!/usr/bin/env python3
"""
OpenRouter API integration for DeepCompanion
Handles communication with OpenRouter cloud models
"""

import requests
import json
import threading
from datetime import datetime
from typing import Dict, Any, Callable, Optional
from config import OPENROUTER_CONFIG, get_openrouter_headers, get_model_config

class OpenRouterClient:
    """Client for OpenRouter API with streaming support"""
    
    def __init__(self, parent_app=None, api_key: str = ""):
        self.parent = parent_app
        self.api_key = api_key  # For backward compatibility
        self.base_url = OPENROUTER_CONFIG["base_url"]
        self.is_streaming = False
        self.current_request = None
        
    def prepare_messages(self, message: str, chat_history: list, system_prompt: Optional[str] = None) -> list:
        """Prepare messages for OpenRouter API"""
        messages = []
        
        # Add system message if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add chat history (keep last 10 messages for context)
        recent_history = chat_history[-10:] if len(chat_history) > 10 else chat_history
        for msg in recent_history:
            messages.append(msg)
        
        # Add current message
        messages.append({"role": "user", "content": message})
        
        return messages
    
    def get_system_prompt(self, model_category: str) -> str:
        """Get appropriate system prompt based on model category"""
        prompts = {
            "general": "You are a helpful, knowledgeable AI assistant. Provide clear, accurate, and engaging responses.",
            "reasoning": "You are an advanced AI focused on deep reasoning and analysis. Think step by step and provide detailed explanations.",
            "coding": "You are an expert programming assistant. Provide clean, well-documented code with explanations and best practices.",
            "research": "You are a research assistant with access to current information. Provide comprehensive, well-sourced answers."
        }
        return prompts.get(model_category, prompts["general"])
    
    def stream_chat_completion(
        self, 
        model_name: str, 
        message: str, 
        chat_history: Optional[list] = None,
        on_token: Optional[Callable[[str], None]] = None,
        on_complete: Optional[Callable[[str, Dict], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        **kwargs
    ):
        """Stream chat completion from OpenRouter"""
        if chat_history is None:
            chat_history = []
            
        try:
            # Get model configuration
            model_config = get_model_config(model_name)
            if not model_config:
                if on_error:
                    on_error(f"Model {model_name} not configured")
                return
            
            # Prepare request
            headers = get_openrouter_headers(model_name)
            system_prompt = self.get_system_prompt(model_config.get("category", "general"))
            messages = self.prepare_messages(message, chat_history, system_prompt)
            
            # Request payload
            payload = {
                "model": model_name,
                "messages": messages,
                "stream": True,
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", model_config.get("max_tokens", 4096)),
                "top_p": kwargs.get("top_p", 0.9),
            }
            
            # Make streaming request
            self.is_streaming = True
            start_time = datetime.now()
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                stream=True,
                timeout=120
            )
            
            if response.status_code == 200:
                full_response = ""
                token_count = 0
                
                for line in response.iter_lines():
                    if not self.is_streaming:
                        break
                        
                    if line:
                        line = line.decode('utf-8')
                        
                        # Skip non-data lines
                        if not line.startswith('data: '):
                            continue
                            
                        # Extract JSON data
                        data_str = line[6:]  # Remove 'data: ' prefix
                        
                        # Check for end of stream
                        if data_str.strip() == '[DONE]':
                            break
                            
                        try:
                            data = json.loads(data_str)
                            
                            # Extract content from delta
                            if 'choices' in data and len(data['choices']) > 0:
                                choice = data['choices'][0]
                                if 'delta' in choice and 'content' in choice['delta']:
                                    content = choice['delta']['content']
                                    if content:
                                        full_response += content
                                        token_count += 1
                                        
                                        # Call token callback
                                        if on_token:
                                            on_token(content)
                                            
                        except json.JSONDecodeError:
                            continue
                
                # Calculate metrics
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                metrics = {
                    "total_time": duration,
                    "token_count": token_count,
                    "tokens_per_second": token_count / duration if duration > 0 else 0,
                    "model": model_name,
                    "provider": "OpenRouter"
                }
                
                # Call completion callback
                if on_complete:
                    on_complete(full_response, metrics)
                    
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                if on_error:
                    on_error(error_msg)
                    
        except requests.exceptions.Timeout:
            if on_error:
                on_error("Request timed out")
        except requests.exceptions.RequestException as e:
            if on_error:
                on_error(f"Request failed: {str(e)}")
        except Exception as e:
            if on_error:
                on_error(f"Unexpected error: {str(e)}")
        finally:
            self.is_streaming = False
    
    def stop_streaming(self):
        """Stop current streaming request"""
        self.is_streaming = False
        
    def get_available_models(self) -> Dict[str, Dict]:
        """Get list of available models"""
        return OPENROUTER_CONFIG["models"]
        
    def test_connection(self, model_name: Optional[str] = None) -> bool:
        """Test connection to OpenRouter API"""
        try:
            # Use first available model if none specified
            if not model_name:
                model_name = list(OPENROUTER_CONFIG["models"].keys())[0]
                
            headers = get_openrouter_headers(model_name)
            
            # Simple test request
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 10,
                "stream": False
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception:
            return False

class OpenRouterModelWrapper:
    """Wrapper to integrate OpenRouter with DeepCompanion's model system"""
    
    def __init__(self, parent_app):
        self.parent = parent_app
        self.client = OpenRouterClient(parent_app)
        self.response_buffer = ""
        self.chunk_buffer = ""
        
    def get_openrouter_response_wrapped(self, message: str, model_name: str):
        """Wrapper method compatible with DeepCompanion's threading system"""
        
        def on_token(content):
            """Handle streaming tokens"""
            if self.parent:
                self.parent.root.after(0, lambda: self.parent.update_streaming_message(content))
        
        def on_complete(response, metrics):
            """Handle completion"""
            if self.parent:
                # Add to chat history
                self.parent.chat_history.append({"role": "assistant", "content": response})
                self.parent.chat_histories[self.parent.current_model_key] = self.parent.chat_history.copy()
                
                # Update status with metrics
                status_msg = f"✅ {metrics['model']} ({metrics['total_time']:.1f}s @ {metrics['tokens_per_second']:.1f} tok/s) ☁️"
                self.parent.root.after(0, lambda: self.parent.update_status(status_msg, "green"))
                self.parent.root.after(0, self.parent.finalize_streaming_message)
        
        def on_error(error):
            """Handle errors"""
            if self.parent:
                error_display = f"❌ OpenRouter Error\n\n{error}\n\n💡 Suggestions:\n• Check your internet connection\n• Verify API key is valid\n• Try a different model"
                self.parent.root.after(0, lambda: self.parent.add_message_to_chat("System", error_display, "assistant"))
                self.parent.root.after(0, lambda: self.parent.update_status("❌ Cloud API Error", "red"))
        
        # Initialize streaming display
        if self.parent:
            self.parent.root.after(0, lambda: self.parent.add_streaming_message_start())
        
        # Start streaming
        self.client.stream_chat_completion(
            model_name=model_name,
            message=message,
            chat_history=self.parent.chat_history if self.parent else [],
            on_token=on_token,
            on_complete=on_complete,
            on_error=on_error
        )
