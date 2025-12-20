#!/usr/bin/env python3
"""
Companion API Wrapper
Unified wrapper for LLM APIs and Search Engines with fast switching and load balancing
"""

import requests
import json
import time
import logging
import threading
import os
import sys
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import random

# Add parent directory to path to import the OpenRouter client
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import existing modules
try:
    from search_engine_wrapper import search_wrapper, SearchResult
except ImportError:
    from website.search_engine_wrapper import search_wrapper, SearchResult

try:
    from openrouter_client import OpenRouterClient
    from config import (get_openrouter_headers, get_model_config, 
                       OPENROUTER_CONFIG, OLLAMA_CONFIG, GROQ_CONFIG, HUGGINGFACE_CONFIG)
except ImportError:
    # If running from website directory
    import sys
    import os
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(parent_dir)
    from openrouter_client import OpenRouterClient
    from config import (get_openrouter_headers, get_model_config, 
                       OPENROUTER_CONFIG, OLLAMA_CONFIG, GROQ_CONFIG, HUGGINGFACE_CONFIG)

logger = logging.getLogger(__name__)

@dataclass
class APIResponse:
    """Standardized response from any API"""
    content: str
    source: str
    model: str
    thinking_data: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    links: Optional[List[Dict[str, str]]] = None
    success: bool = True
    error: Optional[str] = None
    response_time: float = 0.0

@dataclass
class LLMProvider:
    """LLM provider configuration"""
    name: str
    models: List[str]
    endpoint: str
    headers: Dict[str, str]
    priority: int = 1
    active: bool = True
    rate_limit: int = 60  # requests per minute
    last_used: Optional[datetime] = None
    success_rate: float = 1.0

def call_ollama_local(message: str, chat_history: Optional[List[Dict]] = None, model: Optional[str] = None) -> Optional[APIResponse]:
    """
    Call local Ollama LLM as fallback when cloud APIs fail
    
    Args:
        message: User message
        chat_history: Previous conversation history
        model: Specific model to use (default: llama3.2:3b)
        
    Returns:
        APIResponse or None if Ollama is not available
    """
    try:
        if model is None:
            model = OLLAMA_CONFIG["default_model"]
        
        # Check if Ollama is running
        base_url = OLLAMA_CONFIG["base_url"]
        try:
            health_check = requests.get(f"{base_url}/api/tags", timeout=2)
            if health_check.status_code != 200:
                logger.warning("🔴 Ollama service not responding")
                return None
        except requests.exceptions.RequestException:
            logger.warning("🔴 Ollama service not available at {base_url}")
            return None
        
        # Prepare chat messages
        messages = []
        
        # Add chat history (last 5 messages to keep context)
        if chat_history:
            for msg in chat_history[-5:]:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
        
        # Add current message
        messages.append({
            "role": "user",
            "content": message
        })
        
        # Call Ollama chat API
        start_time = time.time()
        logger.info(f"🦙 Calling local Ollama model: {model}")
        
        response = requests.post(
            f"{base_url}{OLLAMA_CONFIG['chat_endpoint']}",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "num_predict": 2048
                }
            },
            timeout=OLLAMA_CONFIG["timeout"]
        )
        
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            content = data.get("message", {}).get("content", "")
            
            if content:
                logger.info(f"✅ Ollama responded in {response_time:.2f}s")
                model_info = OLLAMA_CONFIG["models"].get(model, {})
                
                return APIResponse(
                    content=content,
                    source=f"Local Ollama ({model_info.get('display_name', model)})",
                    model=model,
                    success=True,
                    metadata={
                        'local': True,
                        'provider': 'ollama',
                        'model_info': model_info,
                        'response_time': response_time
                    },
                    response_time=response_time
                )
            else:
                logger.warning(f"⚠️ Ollama returned empty response")
                return None
        else:
            logger.warning(f"❌ Ollama error: HTTP {response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        logger.warning(f"⏱️ Ollama timeout after {OLLAMA_CONFIG['timeout']}s")
        return None
    except Exception as e:
        logger.error(f"❌ Ollama error: {str(e)}")
        return None

def call_groq_api(message: str, chat_history: Optional[List[Dict]] = None, model: Optional[str] = None) -> Optional[APIResponse]:
    """
    Call Groq API - Ultra-fast cloud inference (up to 800 tokens/sec)
    
    Args:
        message: User message
        chat_history: Previous conversation history
        model: Specific model to use (default: llama-3.3-70b-versatile)
        
    Returns:
        APIResponse or None if Groq API fails
    """
    try:
        if model is None:
            model = GROQ_CONFIG["default_model"]
        
        # Prepare chat messages
        messages = []
        
        # Add chat history (last 10 messages for context)
        if chat_history:
            for msg in chat_history[-10:]:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
        
        # Add current message
        messages.append({
            "role": "user",
            "content": message
        })
        
        # Call Groq API
        start_time = time.time()
        logger.info(f"⚡ Calling Groq API with model: {model}")
        
        response = requests.post(
            f"{GROQ_CONFIG['base_url']}/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_CONFIG['api_key']}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 2048,
                "top_p": 0.9,
                "stream": False
            },
            timeout=GROQ_CONFIG["timeout"]
        )
        
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            if content:
                model_info = GROQ_CONFIG["models"].get(model, {})
                logger.info(f"✅ Groq responded in {response_time:.2f}s ({int(len(content.split())/response_time)} words/sec)")
                
                return APIResponse(
                    content=content,
                    source=f"Groq ({model_info.get('display_name', model)})",
                    model=model,
                    success=True,
                    metadata={
                        'provider': 'groq',
                        'model_info': model_info,
                        'response_time': response_time,
                        'speed': model_info.get('speed', 'fast'),
                        'usage': data.get('usage', {})
                    },
                    response_time=response_time
                )
            else:
                logger.warning(f"⚠️ Groq returned empty response")
                return None
        else:
            error_msg = response.text
            logger.warning(f"❌ Groq error: HTTP {response.status_code} - {error_msg}")
            return None
            
    except requests.exceptions.Timeout:
        logger.warning(f"⏱️ Groq timeout after {GROQ_CONFIG['timeout']}s")
        return None
    except Exception as e:
        logger.error(f"❌ Groq error: {str(e)}")
        return None

def call_huggingface_api(message: str, chat_history: Optional[List[Dict]] = None, model: Optional[str] = None) -> Optional[APIResponse]:
    """
    Call Hugging Face Inference API - Free tier with 1000+ models
    
    Args:
        message: User message
        chat_history: Previous conversation history
        model: Specific model to use (default: meta-llama/Llama-3.2-3B-Instruct)
        
    Returns:
        APIResponse or None if Hugging Face API fails
    """
    try:
        # Check if API key is configured
        if not HUGGINGFACE_CONFIG.get("api_key"):
            logger.warning("⚠️ Hugging Face API key not configured, skipping")
            return None
            
        if model is None:
            model = HUGGINGFACE_CONFIG["default_model"]
        
        # Prepare the prompt (HF uses simpler format)
        prompt = message
        if chat_history:
            # Add last 3 messages for context
            context = ""
            for msg in chat_history[-3:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                context += f"{role}: {content}\n"
            prompt = f"{context}\nuser: {message}\nassistant:"
        
        # Call Hugging Face API
        start_time = time.time()
        logger.info(f"🤗 Calling Hugging Face API with model: {model}")
        
        response = requests.post(
            f"{HUGGINGFACE_CONFIG['base_url']}/{model}",
            headers={
                "Authorization": f"Bearer {HUGGINGFACE_CONFIG['api_key']}",
                "Content-Type": "application/json"
            },
            json={
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": 512,
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "return_full_text": False
                }
            },
            timeout=HUGGINGFACE_CONFIG["timeout"]
        )
        
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            # HF returns array with generated text
            content = ""
            if isinstance(data, list) and len(data) > 0:
                content = data[0].get("generated_text", "")
            elif isinstance(data, dict):
                content = data.get("generated_text", "")
            
            if content:
                model_info = HUGGINGFACE_CONFIG["models"].get(model, {})
                logger.info(f"✅ Hugging Face responded in {response_time:.2f}s")
                
                return APIResponse(
                    content=content.strip(),
                    source=f"Hugging Face ({model_info.get('display_name', model.split('/')[-1])})",
                    model=model,
                    success=True,
                    metadata={
                        'provider': 'huggingface',
                        'model_info': model_info,
                        'response_time': response_time
                    },
                    response_time=response_time
                )
            else:
                logger.warning(f"⚠️ Hugging Face returned empty response")
                return None
        elif response.status_code == 503:
            logger.warning(f"⚠️ Hugging Face model {model} is loading, try again in a moment")
            return None
        else:
            error_msg = response.text
            logger.warning(f"❌ Hugging Face error: HTTP {response.status_code} - {error_msg}")
            return None
            
    except requests.exceptions.Timeout:
        logger.warning(f"⏱️ Hugging Face timeout after {HUGGINGFACE_CONFIG['timeout']}s")
        return None
    except Exception as e:
        logger.error(f"❌ Hugging Face error: {str(e)}")
        return None

class CompanionAPIWrapper:
    """Unified API wrapper for all Companion services"""
    
    def __init__(self):
        import os
        api_key = os.environ.get('OPENROUTER_API_KEY', '')
        self.openrouter_client = OpenRouterClient(api_key=api_key)
        self.search_wrapper = search_wrapper
        
        # Initialize LLM providers with load balancing (Updated Nov 2025)
        self.llm_providers = {
            'openrouter': LLMProvider(
                name='OpenRouter',
                models=[
                    # New Working Free Models (November 2025)
                    "alibaba/tongyi-deepresearch-30b-a3b:free",
                    "deepseek/deepseek-chat-v3.1:free",
                    "openai/gpt-oss-20b:free"
                ],
                endpoint=OPENROUTER_CONFIG["base_url"],
                headers={},  # Headers will be set per request
                priority=1
            )
        }
        
        # Model categories for intelligent routing (New working free models)
        self.model_categories = {
            'reasoning': [
                "alibaba/tongyi-deepresearch-30b-a3b:free",
                "deepseek/deepseek-chat-v3.1:free",
                "openai/gpt-oss-20b:free"
            ],
            'research': [
                "alibaba/tongyi-deepresearch-30b-a3b:free",
                "deepseek/deepseek-chat-v3.1:free",
                "openai/gpt-oss-20b:free"
            ],
            'coding': [
                "deepseek/deepseek-chat-v3.1:free",
                "openai/gpt-oss-20b:free",
                "alibaba/tongyi-deepresearch-30b-a3b:free"
            ],
            'general': [
                "deepseek/deepseek-chat-v3.1:free",
                "openai/gpt-oss-20b:free",
                "alibaba/tongyi-deepresearch-30b-a3b:free"
            ],
            'fast': [
                "openai/gpt-oss-20b:free",
                "deepseek/deepseek-chat-v3.1:free",
                "alibaba/tongyi-deepresearch-30b-a3b:free"
            ],
            'multilingual': [
                "deepseek/deepseek-chat-v3.1:free",
                "alibaba/tongyi-deepresearch-30b-a3b:free",
                "sarvamai/sarvam-m:free",
                "google/gemini-2.0-flash-exp:free",
                "google/gemma-3n-e2b-it:free"
            ],
            'large_context': [
                "moonshotai/kimi-dev-72b:free",
                "nvidia/llama-3.1-nemotron-ultra-253b-v1:free",
                "featherless/qwerky-72b:free",
                "moonshotai/kimi-k2:free",
                "qwen/qwen3-coder:free"
            ]
        }
        
        # Performance tracking
        self.model_performance = {}
        self.rate_limits = {}
        self.circuit_breakers = {}
        
        # Cache for responses with intelligent TTL
        self.response_cache = {}
        self.cache_ttl = 300  # 5 minutes default
        
        # Time-sensitive query patterns and their cache durations
        self.time_sensitive_patterns = {
            # Financial/Price data - expire daily
            'financial': {
                'patterns': ['price', 'cost', 'salary', 'wage', 'tax', 'gst', 'vat', 'rate', 'stock', 'crypto', 'currency', 'exchange'],
                'cache_duration': 86400,  # 1 day
                'description': 'Financial and pricing information'
            },
            # Specifications/Technical - expire weekly
            'technical': {
                'patterns': ['specs', 'specification', 'technical details', 'datasheet', 'dimensions', 'weight', 'performance', 'benchmark'],
                'cache_duration': 604800,  # 7 days
                'description': 'Technical specifications and data'
            },
            # Current events/News - expire hourly
            'current_events': {
                'patterns': ['news', 'current', 'latest', 'today', 'recent', 'update', 'breaking', 'announced'],
                'cache_duration': 3600,  # 1 hour
                'description': 'Current events and news'
            },
            # Government/Legal - expire monthly
            'regulatory': {
                'patterns': ['law', 'legal', 'regulation', 'policy', 'government', 'compliance', 'license', 'permit'],
                'cache_duration': 2592000,  # 30 days
                'description': 'Legal and regulatory information'
            },
            # Weather/Environmental - expire every 6 hours
            'environmental': {
                'patterns': ['weather', 'temperature', 'climate', 'forecast', 'pollution', 'air quality'],
                'cache_duration': 21600,  # 6 hours
                'description': 'Weather and environmental data'
            },
            # Business/Company info - expire weekly
            'business': {
                'patterns': ['company', 'business', 'revenue', 'earnings', 'quarterly', 'annual report', 'market cap'],
                'cache_duration': 604800,  # 7 days
                'description': 'Business and company information'
            }
        }
        
        logger.info("🚀 Companion API Wrapper initialized with unified LLM and search capabilities")
        logger.info(f"⏰ Intelligent caching enabled for {len(self.time_sensitive_patterns)} data categories")
    
    def get_optimal_model(self, category: str = 'general', exclude_models: Optional[List[str]] = None) -> str:
        """Get the optimal model for a given category with load balancing"""
        if exclude_models is None:
            exclude_models = []
        
        available_models = [
            model for model in self.model_categories.get(category, self.model_categories['general'])
            if model not in exclude_models and not self._is_rate_limited(model)
        ]
        
        if not available_models:
            # Fallback to any available model
            available_models = [
                model for models in self.model_categories.values() 
                for model in models 
                if model not in exclude_models and not self._is_rate_limited(model)
            ]
        
        if not available_models:
            return self.model_categories['general'][0]  # Ultimate fallback
        
        # Choose based on performance and load balancing
        best_model = self._select_best_performing_model(available_models)
        logger.info(f"🎯 Selected optimal model: {best_model} for category: {category}")
        return best_model
    
    def _select_best_performing_model(self, models: List[str]) -> str:
        """Select the best performing model from available options"""
        if not models:
            return self.model_categories['general'][0]  # Fallback
        
        model_scores = {}
        
        for model in models:
            performance = self.model_performance.get(model, {})
            success_rate = performance.get('success_rate', 1.0)
            avg_response_time = performance.get('avg_response_time', 1.0)
            last_used = performance.get('last_used', datetime.min)
            
            # Calculate score (higher is better)
            time_penalty = (datetime.now() - last_used).seconds / 3600  # Hours since last use
            score = success_rate * 100 - avg_response_time + time_penalty * 0.1
            model_scores[model] = score
        
        # Return model with highest score
        if model_scores:
            best_model = max(model_scores.keys(), key=lambda k: model_scores[k])
            return best_model
        else:
            return models[0]
    
    def _is_time_sensitive_query(self, message: str) -> tuple:
        """
        Check if a query is time-sensitive and requires web search
        Returns: (is_time_sensitive, category, cache_duration)
        """
        message_lower = message.lower()
        
        # Skip time-sensitive detection for image analysis requests
        if any(indicator in message for indicator in ['🖼️', 'Image:', 'image:', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']):
            logger.info("📸 Image analysis request detected - skipping time-sensitive detection")
            return False, '', 0
        
        for category, config in self.time_sensitive_patterns.items():
            for pattern in config['patterns']:
                if pattern in message_lower:
                    logger.info(f"⏰ Time-sensitive query detected: {category} - {config['description']}")
                    return True, category, config['cache_duration']
        
        # Additional heuristics for time-sensitive queries
        time_indicators = ['current', 'latest', 'today', 'now', '2024', '2025', 'recent']
        sensitive_keywords = ['price', 'cost', 'tax', 'specification', 'specs', 'review']
        
        has_time_indicator = any(indicator in message_lower for indicator in time_indicators)
        has_sensitive_keyword = any(keyword in message_lower for keyword in sensitive_keywords)
        
        if has_time_indicator and has_sensitive_keyword:
            logger.info("⏰ Time-sensitive query detected via heuristics")
            return True, 'general_time_sensitive', 86400  # 1 day cache
        
        return False, '', 0

    def _get_intelligent_cache_duration(self, message: str, category: str = 'general') -> int:
        """Get intelligent cache duration based on query type"""
        is_time_sensitive, time_category, duration = self._is_time_sensitive_query(message)
        
        if is_time_sensitive:
            return duration
        
        # Default cache durations by category
        default_durations = {
            'general': 3600,      # 1 hour
            'reasoning': 7200,    # 2 hours  
            'coding': 86400,      # 1 day
            'research': 43200,    # 12 hours
            'fast': 1800          # 30 minutes
        }
        
        return default_durations.get(category, 3600)

    def _should_force_web_search(self, message: str, tools: List[str]) -> bool:
        """Determine if web search should be forced for this query"""
        # Always force web search for time-sensitive queries
        is_time_sensitive, _, _ = self._is_time_sensitive_query(message)
        if is_time_sensitive:
            return True
        
        # Force web search for specific patterns
        force_patterns = [
            'price of', 'cost of', 'how much', 'specs of', 'specifications of',
            'latest', 'current', 'today', 'now', 'recent', 'new', 'updated',
            'review of', 'comparison', 'vs', 'versus', 'buy', 'purchase'
        ]
        
        message_lower = message.lower()
        if any(pattern in message_lower for pattern in force_patterns):
            logger.info(f"🔍 Forcing web search due to pattern match")
            return True
        
        # Force web search if no specific tools are selected (general query)
        if not tools or tools == []:
            # Check for queries that likely need current information
            current_info_indicators = ['where to', 'how to buy', 'best', 'top', 'recommend']
            if any(indicator in message_lower for indicator in current_info_indicators):
                return True
        
        return False
    
    def _is_rate_limited(self, model: str) -> bool:
        """Check if model is currently rate limited"""
        rate_limit_info = self.rate_limits.get(model)
        if not rate_limit_info:
            return False
        
        reset_time = rate_limit_info.get('reset_time', datetime.min)
        return datetime.now() < reset_time
    
    def _update_performance_metrics(self, model: str, response_time: float, success: bool):
        """Update performance metrics for a model"""
        if model not in self.model_performance:
            self.model_performance[model] = {
                'success_rate': 1.0,
                'avg_response_time': response_time,
                'total_requests': 0,
                'successful_requests': 0,
                'last_used': datetime.now()
            }
        
        metrics = self.model_performance[model]
        metrics['total_requests'] += 1
        metrics['last_used'] = datetime.now()
        
        if success:
            metrics['successful_requests'] += 1
        
        metrics['success_rate'] = metrics['successful_requests'] / metrics['total_requests']
        metrics['avg_response_time'] = (metrics['avg_response_time'] + response_time) / 2
    
    def generate_response(
        self, 
        message: str, 
        category: str = 'general',
        tools: Optional[List[str]] = None,
        chat_history: Optional[List[Dict]] = None,
        max_retries: int = 3
    ) -> APIResponse:
        """Generate response using the best available model with automatic fallback"""
        if tools is None:
            tools = []
        if chat_history is None:
            chat_history = []
        
        # Special handling for image analysis requests
        if any(indicator in message for indicator in ['🖼️', 'Image:', 'image:', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']):
            logger.info("📸 Image analysis request detected - using vision-capable model")
            # Use a vision-capable model for image analysis
            selected_model = self.get_optimal_model('reasoning')  # Use reasoning models as they often have vision
            return self._call_llm_model(selected_model, message, chat_history, tools)
        
        # Check for time-sensitive queries and auto-add web search
        is_time_sensitive, time_category, cache_duration = self._is_time_sensitive_query(message)
        should_force_web = self._should_force_web_search(message, tools)
        
        if is_time_sensitive or should_force_web:
            if 'web' not in tools and 'deepsearch' not in tools and 'research' not in tools:
                tools.append('web')
                logger.info(f"🔍 Auto-enabled web search for time-sensitive/current query: {time_category if is_time_sensitive else 'forced'}")
        
        # Use intelligent cache duration
        intelligent_cache_duration = self._get_intelligent_cache_duration(message, category)
        cache_key = f"{message}:{category}:{':'.join(sorted(tools))}"
        
        # Check cache with intelligent TTL
        cached_response = self._get_cached_response_with_ttl(cache_key, intelligent_cache_duration)
        if cached_response:
            logger.info(f"💾 Returning cached response (TTL: {intelligent_cache_duration}s)")
            return cached_response
        
        # Initialize web result holder
        web_response = None
        
        # Handle web search tools - always perform search for these tools
        if 'web' in tools or 'deepsearch' in tools or 'research' in tools:
            is_deep_search = 'deepsearch' in tools or 'research' in tools or is_time_sensitive
            web_response = self._handle_web_search(message, deep_search=is_deep_search)
            
            # For time-sensitive queries, prioritize web results
            if is_time_sensitive and web_response.success:
                logger.info(f"⏰ Prioritizing web results for time-sensitive {time_category} query")
                # Still get LLM analysis but web data takes precedence
            
            if set(tools) == {'web'}:
                # Web-only mode - return search results immediately
                self._cache_response_with_ttl(cache_key, web_response, intelligent_cache_duration)
                return web_response
        
        # Determine model category based on tools
        logger.info(f"🔧 Tools received in generate_response: {tools}")
        if 'deepthink' in tools:
            # Deep Think mode uses ALL available models and search engines
            logger.info("🧠⚡ TRIGGERING DEEP THINK MODE")
            return self._handle_deepthink_mode(message, chat_history)
        elif 'think' in tools:
            category = 'reasoning'
        elif 'deepsearch' in tools or 'research' in tools:
            category = 'research'
        elif 'code' in tools:
            category = 'coding'
        elif 'fast' in tools:
            category = 'fast'
        
        # Try multiple models with fallback
        attempted_models = []
        llm_response = None
        model = None  # Initialize model variable
        
        for attempt in range(max_retries):
            try:
                model = self.get_optimal_model(category, exclude_models=attempted_models)
                attempted_models.append(model)
                
                start_time = time.time()
                response = self._call_llm_model(model, message, chat_history, tools)
                response_time = time.time() - start_time
                
                if response.success:
                    self._update_performance_metrics(model, response_time, True)
                    llm_response = response
                    break
                else:
                    self._update_performance_metrics(model, response_time, False)
                    logger.warning(f"❌ Model {model} failed: {response.error}")
                    
            except Exception as e:
                if model:
                    logger.error(f"❌ Error with model {model}: {str(e)}")
                    self._update_performance_metrics(model, 10.0, False)  # Penalty for errors
                else:
                    logger.error(f"❌ Error during model selection: {str(e)}")
        
        # Combine LLM and web results with smart prioritization
        if llm_response and llm_response.success and web_response and web_response.success:
            # For time-sensitive queries, prioritize web data
            if is_time_sensitive:
                combined_content = f"🔍 **Current Information ({time_category.replace('_', ' ').title()}):**\n\n{web_response.content}\n\n---\n\n🤖 **AI Analysis:**\n\n{llm_response.content}"
            elif 'research' in tools or 'deepsearch' in tools:
                combined_content = f"🤖 **AI Analysis:**\n\n{llm_response.content}\n\n---\n\n{web_response.content}"
            else:
                # For general web search, add web results after AI response
                combined_content = f"{llm_response.content}\n\n{web_response.content}"
            
            combined_response = APIResponse(
                content=combined_content,
                source=f"{llm_response.source} + Web Research",
                model=f"{llm_response.model} + Multi-Engine Search",
                thinking_data=llm_response.thinking_data,
                links=web_response.links,
                metadata={
                    'llm_model': llm_response.model,
                    'web_sources': web_response.metadata.get('sources', []) if web_response.metadata else [],
                    'combined_response': True,
                    'time_sensitive': is_time_sensitive,
                    'cache_duration': intelligent_cache_duration
                },
                success=True
            )
            
            self._cache_response_with_ttl(cache_key, combined_response, intelligent_cache_duration)
            return combined_response
        
        # Return LLM response if available
        elif llm_response and llm_response.success:
            self._cache_response_with_ttl(cache_key, llm_response, intelligent_cache_duration)
            return llm_response
        
        # Return web response if LLM failed but web succeeded
        elif web_response and web_response.success:
            self._cache_response_with_ttl(cache_key, web_response, intelligent_cache_duration)
            return web_response
        
        # All cloud APIs failed, use intelligent fallback (Groq → Ollama → static)
        logger.warning("🔄 OpenRouter failed, activating fallback chain (Groq → Ollama → Static)...")
        fallback_response = self.generate_intelligent_fallback_response(message, chat_history)
        self._cache_response_with_ttl(cache_key, fallback_response, intelligent_cache_duration)
        return fallback_response
    
    def generate_intelligent_fallback_response(self, message: str, chat_history: Optional[List[Dict]] = None) -> APIResponse:
        """Generate intelligent fallback response when all APIs fail
        
        Five-tier fallback strategy:
        1. Try Groq API (ultra-fast, free, 14k requests/day)
        2. Try Hugging Face (1000+ free models)
        3. Try local Ollama LLM (unlimited, private, no internet)
        4. Try alternative Ollama models if first fails
        5. Use static intelligent responses as last resort
        """
        if chat_history is None:
            chat_history = []
        
        # TIER 1: Try Groq API first (fastest cloud option)
        logger.info("⚡ Attempting Groq API fallback...")
        for model in GROQ_CONFIG["fallback_models"]:
            groq_response = call_groq_api(message, chat_history, model)
            if groq_response and groq_response.success:
                logger.info(f"✅ Groq fallback successful with {model}")
                return groq_response
        
        logger.warning("⚠️ Groq API fallback failed, trying Hugging Face...")
        
        # TIER 2: Try Hugging Face API
        if HUGGINGFACE_CONFIG.get("api_key"):
            logger.info("🤗 Attempting Hugging Face API fallback...")
            for model in HUGGINGFACE_CONFIG["fallback_models"]:
                hf_response = call_huggingface_api(message, chat_history, model)
                if hf_response and hf_response.success:
                    logger.info(f"✅ Hugging Face fallback successful with {model}")
                    return hf_response
        else:
            logger.info("⚠️ Hugging Face API key not configured, skipping")
        
        logger.warning("⚠️ Cloud APIs failed, trying local Ollama...")
        
        # TIER 3: Try local Ollama models
        logger.info("🦙 Attempting local Ollama fallback...")
        for model in OLLAMA_CONFIG["fallback_models"]:
            ollama_response = call_ollama_local(message, chat_history, model)
            if ollama_response and ollama_response.success:
                logger.info(f"✅ Local Ollama fallback successful with {model}")
                return ollama_response
        
        logger.warning("⚠️ All LLM fallbacks failed, using static responses")
        
        # TIER 3 & 4: Static intelligent responses (existing logic)
        message_lower = message.lower()
        
        # Check if it's a coding question
        if any(word in message_lower for word in ['code', 'programming', 'function', 'python', 'javascript']):
            content = """I can help you with programming! Here are some ways I can assist:

**Programming Languages I Support:**
• Python - Data science, web development, automation
• JavaScript - Frontend/backend web development
• HTML/CSS - Web structure and styling
• SQL - Database queries
• Java, C++, C# - Enterprise and system programming

**What I Can Help With:**
• Code examples and templates
• Debugging assistance
• Best practices and patterns
• Algorithm explanations
• Project structure guidance

What specific programming topic would you like to explore?"""
        
        elif any(word in message_lower for word in ['calculate', 'math', 'equation']):
            content = """I can help with mathematical calculations and problem-solving!

**Mathematical Areas I Cover:**
• Basic arithmetic and algebra
• Calculus and derivatives
• Statistics and probability
• Geometry and trigonometry
• Logic and discrete mathematics

**Programming Calculators:**
I can provide calculator code in various languages:
• Python calculator scripts
• JavaScript web calculators
• C/C++ console calculators
• HTML/CSS calculator interfaces

What type of calculation or mathematical concept would you like help with?"""
        
        elif any(word in message_lower for word in ['explain', 'what is', 'how does', 'definition']):
            content = f"""I'd be happy to explain "{message}" for you!

**I can provide explanations on:**
• Technical concepts and terminology
• Step-by-step processes
• Scientific principles
• Programming concepts
• Historical context and background

**My Explanation Style:**
• Clear, jargon-free language
• Real-world examples
• Visual analogies when helpful
• Multiple perspectives when relevant

Could you be more specific about what aspect you'd like me to focus on? This helps me give you the most useful explanation."""
        
        elif any(word in message_lower for word in ['hello', 'hi', 'hey', 'greetings']):
            content = """Hello! I'm Companion AI, your advanced multi-engine AI assistant. 

**What I Can Do:**
🧠 **Think Mode** - Step-by-step reasoning for complex problems
🔍 **Deep Search** - Multi-engine web research and analysis
💻 **Code Mode** - Programming help in multiple languages
🌐 **Web Search** - Real-time information from multiple sources
📁 **File Integration** - Upload files and connect GitHub repos

**Current Status:**
I'm currently running in enhanced fallback mode, which means I can still provide comprehensive help based on my training, though with limited access to real-time AI models.

How can I assist you today?"""
        
        else:
            # Generic helpful response
            content = f"""I understand you're asking about: "{message}"

While I'm currently in fallback mode, I can still help with:

📚 **Learning & Explanation**
• Breaking down complex topics
• Step-by-step tutorials
• Concept clarification

💻 **Programming & Tech**
• Code examples in multiple languages
• Debugging assistance
• Best practices and patterns

🧠 **Problem Solving**
• Analytical thinking
• Creative solutions
• Research guidance

✍️ **Writing & Communication**
• Content creation
• Editing and improvement
• Structured thinking

For your question about "{message}": Could you provide more context or specify what aspect you'd like me to focus on? This helps me give you the most relevant and useful response.

The desktop version of Companion has access to more advanced AI capabilities for even better assistance!"""
        
        return APIResponse(
            content=content,
            source="Companion AI (Fallback Mode)",
            model="Enhanced Fallback",
            success=True,
            metadata={'fallback': True}
        )
    
    def _call_llm_model(
        self, 
        model: str, 
        message: str, 
        chat_history: List[Dict],
        tools: List[str]
    ) -> APIResponse:
        """Call a specific LLM model"""
        try:
            # Prepare system prompt based on tools
            system_prompt = self._generate_system_prompt(tools)
            
            # Prepare messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            # Add recent chat history
            for msg in chat_history[-10:]:
                messages.append(msg)
            
            messages.append({"role": "user", "content": message})
            
            # Call OpenRouter API
            headers = get_openrouter_headers(model)
            headers["HTTP-Referer"] = "https://companion-ai.dev"
            
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 4000,
                "top_p": 0.9,
                "frequency_penalty": 0.1,
                "presence_penalty": 0.1
            }
            
            # Make sync request
            response = requests.post(
                f"{OPENROUTER_CONFIG['base_url']}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # Extract thinking data if present
                thinking_data = self._extract_thinking_data(content)
                
                return APIResponse(
                    content=content,
                    source="Companion AI",
                    model=model.split('/')[-1].title(),  # Hide provider, show clean model name
                    thinking_data=thinking_data,
                    success=True
                )
            else:
                return APIResponse(
                    content="",
                    source="Companion AI",
                    model=model,
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text}"
                )
                        
        except Exception as e:
            return APIResponse(
                content="",
                source="Companion AI", 
                model=model,
                success=False,
                error=str(e)
            )
    
    def _generate_system_prompt(self, tools: List[str]) -> str:
        """Generate system prompt based on active tools"""
        base_prompt = "You are Companion AI, an advanced and helpful AI assistant."
        
        if 'think' in tools:
            base_prompt += " You should think through problems step by step and show your reasoning process."
        
        if 'code' in tools:
            base_prompt += " You should focus on providing code examples, explanations, and programming assistance."
        
        if 'deepsearch' in tools or 'research' in tools:
            base_prompt += " You should provide comprehensive research and analysis on the given topic."
        
        if 'web' in tools:
            base_prompt += " You should consider current information and real-time data in your responses."
        
        base_prompt += " Always be helpful, accurate, and engaging in your responses."
        
        return base_prompt
    
    def _extract_thinking_data(self, content: str) -> Optional[str]:
        """Extract thinking process from response"""
        thinking_patterns = [
            r'<thinking>(.*?)</thinking>',
            r'<think>(.*?)</think>',
            r'\*\*Thinking:\*\*(.*?)(?=\*\*[A-Z]|\n\n|\Z)',
            r'Let me think through this step by step:(.*?)(?=\n\n|\Z)',
        ]
        
        for pattern in thinking_patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _handle_web_search(self, message: str, deep_search: bool = False) -> APIResponse:
        """Handle web search using the search wrapper with enhanced content scraping"""
        try:
            logger.info(f"🔍 Starting {'deep' if deep_search else 'basic'} web search for: {message}")
            
            # Check for ambiguous queries and enhance them
            enhanced_query = self._enhance_search_query(message)
            if enhanced_query != message:
                logger.info(f"🎯 Enhanced query: '{message}' → '{enhanced_query}'")
            
            search_data = self.search_wrapper.enhanced_search_with_mining(enhanced_query, deep_search=deep_search)
            
            if search_data and search_data['results']:
                # Check result relevance - if results seem unrelated, try alternative searches
                relevance_score = self._calculate_result_relevance(message, search_data['results'])
                logger.info(f"📊 Search relevance score: {relevance_score:.2f}")
                
                if relevance_score < 0.3:  # Low relevance threshold
                    logger.info("🔄 Low relevance detected, trying alternative search approaches")
                    alternative_results = self._try_alternative_searches(message)
                    if alternative_results:
                        search_data = alternative_results
                
                # Build comprehensive web result
                web_content_parts = []
                web_links = []
                
                # Add contextual header based on query type
                search_type = "Deep Research Results" if deep_search else "Web Search Results"
                if relevance_score < 0.3:
                    search_type += " (Multiple Search Approaches)"
                
                # Add summary
                if search_data.get('summary'):
                    web_content_parts.append(f"📖 **Summary from {len(search_data['sources'])} Search Engines:**\n{search_data['summary']}")
                
                # Add relevance note for ambiguous queries
                if relevance_score < 0.5:
                    web_content_parts.append(f"ℹ️ **Note:** The query '{message}' returned varied results. Here's what I found across multiple sources:")
                
                # Add key facts
                if search_data.get('key_facts'):
                    web_content_parts.append(f"💡 **Key Facts Discovered:**")
                    for i, fact in enumerate(search_data['key_facts'][:7], 1):
                        web_content_parts.append(f"{i}. {fact}")
                
                # Add search results with enhanced content
                if search_data['results']:
                    sources_str = ", ".join(search_data['sources'])
                    web_content_parts.append(f"🔍 **Search Results (from {sources_str}):**")
                    
                    for i, result in enumerate(search_data['results'][:8], 1):
                        # Safely handle None values
                        title = getattr(result, 'title', '') or f'Result {i}'
                        source = getattr(result, 'source', '') or 'Unknown Source'
                        url = getattr(result, 'url', '')
                        
                        # Format with clickable link if URL is available
                        if url:
                            web_content_parts.append(f"**{i}. [{title}]({url})** (via {source})")
                            web_links.append({'title': title, 'url': url})
                        else:
                            web_content_parts.append(f"**{i}. {title}** (via {source})")
                        
                        # Add snippet
                        snippet = getattr(result, 'snippet', '')
                        if snippet:
                            web_content_parts.append(f"   📝 {snippet}")
                        
                        # Add scraped content preview for deep search
                        content = getattr(result, 'content', '')
                        if deep_search and content and len(content) > 100:
                            preview = content[:300] + "..." if len(content) > 300 else content
                            web_content_parts.append(f"   📄 **Content Preview:** {preview}")
                
                # Add dedicated links section for easier access
                if web_links:
                    web_content_parts.append(f"\n🔗 **Quick Access Links:**")
                    for i, link in enumerate(web_links[:5], 1):
                        web_content_parts.append(f"{i}. [{link['title']}]({link['url']})")
                
                # Add related topics
                if search_data.get('related_topics'):
                    web_content_parts.append(f"🔗 **Related Topics for Further Research:**")
                    for topic in search_data['related_topics'][:10]:
                        web_content_parts.append(f"• {topic}")
                
                content = f"🌐 **{search_type}:**\n\n" + "\n\n".join(web_content_parts)
                
                logger.info(f"✅ Web search complete: {len(search_data['results'])} results, {len(web_links)} links, relevance: {relevance_score:.2f}")
                
                return APIResponse(
                    content=content,
                    source="Companion Web Research",
                    model="Multi-Engine Search + Content Analysis",
                    links=web_links,
                    metadata={
                        'sources': search_data['sources'],
                        'total_results': len(search_data['results']),
                        'deep_search': deep_search,
                        'scraped_content': bool([r for r in search_data['results'] if getattr(r, 'content', '')]),
                        'relevance_score': relevance_score
                    },
                    success=True
                )
            else:
                logger.warning("🌐 No search results found")
                return APIResponse(
                    content="🌐 **No search results found.** Please try rephrasing your query or using different keywords.",
                    source="Companion Web Search",
                    model="Multi-Engine Search",
                    success=False,
                    error="No search results"
                )
                
        except Exception as e:
            logger.error(f"❌ Web search error: {str(e)}")
            return APIResponse(
                content=f"🌐 **Web Search Error:** Unable to search at this time. Error: {str(e)}",
                source="Companion Web Search",
                model="Multi-Engine Search",
                success=False,
                error=str(e)
            )
    
    def _enhance_search_query(self, query: str) -> str:
        """Enhance ambiguous search queries with additional context"""
        query_lower = query.lower().strip()
        
        # Common name queries that might need enhancement
        name_patterns = [
            'who is aryan',
            'aryan who',
            'about aryan',
            'tell me about aryan'
        ]
        
        if any(pattern in query_lower for pattern in name_patterns):
            # Check if this might be about the developer/creator
            if 'aryan' in query_lower and len(query_lower.split()) <= 4:
                # Try multiple search approaches for better coverage
                return f"{query} developer programmer software engineer Companion AI"
        
        # Tech personality queries
        tech_names = ['elon', 'bezos', 'gates', 'jobs', 'torvalds', 'guido']
        if any(name in query_lower for name in tech_names):
            return f"{query} technology entrepreneur biography"
        
        # Academic/research queries
        if any(word in query_lower for word in ['professor', 'researcher', 'scientist', 'phd']):
            return f"{query} academic research publications"
        
        # Company/startup queries
        if any(word in query_lower for word in ['ceo', 'founder', 'startup', 'company']):
            return f"{query} business entrepreneur company profile"
        
        return query
    
    def _calculate_result_relevance(self, original_query: str, results: List) -> float:
        """Calculate how relevant search results are to the original query"""
        if not results:
            return 0.0
        
        query_words = set(original_query.lower().split())
        relevance_scores = []
        
        for result in results[:5]:  # Check top 5 results
            # Safely handle None values for title and snippet
            title = getattr(result, 'title', '') or ''
            snippet = getattr(result, 'snippet', '') or ''
            result_text = f"{title} {snippet}".lower()
            result_words = set(result_text.split())
            
            # Calculate word overlap
            overlap = len(query_words.intersection(result_words))
            total_words = len(query_words)
            
            if total_words > 0:
                relevance_scores.append(overlap / total_words)
            else:
                relevance_scores.append(0.0)
        
        return sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
    
    def _try_alternative_searches(self, original_query: str) -> Optional[dict]:
        """Try alternative search approaches for ambiguous queries"""
        try:
            # For name queries, try different approaches
            if any(word in original_query.lower() for word in ['who is', 'about', 'tell me about']):
                alternatives = [
                    f"{original_query} biography",
                    f"{original_query} developer",
                    f"{original_query} person profile",
                    original_query.replace('who is', '').replace('about', '').strip() + " notable person"
                ]
                
                for alt_query in alternatives:
                    try:
                        alt_results = self.search_wrapper.enhanced_search_with_mining(alt_query, deep_search=False)
                        if alt_results and alt_results['results']:
                            alt_relevance = self._calculate_result_relevance(original_query, alt_results['results'])
                            if alt_relevance > 0.3:
                                logger.info(f"✅ Better results found with alternative query: '{alt_query}'")
                                return alt_results
                    except Exception as e:
                        logger.warning(f"Alternative search failed for '{alt_query}': {e}")
                        continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error in alternative search: {e}")
            return None
    
    def _handle_deepthink_mode(self, message: str, chat_history: List[Dict]) -> APIResponse:
        """
        Deep Think Mode: Uses ALL available LLMs and search engines for comprehensive analysis
        This is the most advanced tool that compares outputs from multiple sources
        """
        logger.info(f"🧠⚡ Starting Deep Think Mode for: {message}")
        
        start_time = time.time()
        
        # Step 1: Enhanced web search
        logger.info("🔍 Phase 1: Comprehensive web research")
        web_responses = []
        
        try:
            web_result = self._handle_web_search(message, deep_search=True)
            if web_result.success:
                web_responses.append({
                    'source': 'Multi-Engine Web Search',
                    'content': web_result.content,
                    'links': web_result.links,
                    'metadata': web_result.metadata
                })
                logger.info(f"✅ Web search successful")
            else:
                logger.warning(f"❌ Web search failed: {web_result.error}")
        except Exception as e:
            logger.warning(f"Web search failed in DeepThink: {e}")
        
        # Step 2: Query multiple LLM models in parallel
        logger.info("🤖 Phase 2: Querying multiple LLM models")
        llm_responses = []
        
        # Get all available models from all categories
        all_models = []
        for category_models in self.model_categories.values():
            all_models.extend(category_models)
        
        # Remove duplicates while preserving order
        unique_models = []
        seen = set()
        for model in all_models:
            if model not in seen:
                unique_models.append(model)
                seen.add(model)
        
        # Limit to top 8 models for manageable analysis
        selected_models = unique_models[:8]
        logger.info(f"🎯 Selected {len(selected_models)} models for analysis")
        
        # Query models with basic error handling
        for model in selected_models:
            try:
                response = self._query_model_for_deepthink(model, message, chat_history)
                if response and response.success:
                    llm_responses.append({
                        'model': model,
                        'content': response.content,
                        'thinking': response.thinking_data,
                        'response_time': response.response_time
                    })
                    logger.info(f"✅ {model}: Success")
                else:
                    logger.warning(f"❌ {model}: Failed")
            except Exception as e:
                logger.warning(f"❌ {model}: Error - {str(e)}")
        
        logger.info(f"📊 DeepThink Phase 2 Complete: {len(llm_responses)} successful LLM responses")
        
        # Step 3: Analysis and synthesis
        logger.info("🧠 Phase 3: Analyzing and synthesizing all responses")
        
        synthesis_result = self._synthesize_deepthink_responses(
            message, web_responses, llm_responses
        )
        
        total_time = time.time() - start_time
        
        # Step 4: Create comprehensive response
        logger.info(f"✨ Deep Think complete in {total_time:.2f}s with {len(llm_responses)} LLM responses")
        
        # Collect all links from web responses
        all_links = []
        for web_resp in web_responses:
            if 'links' in web_resp and web_resp['links']:
                all_links.extend(web_resp['links'])
        
        return APIResponse(
            content=synthesis_result,
            source="Companion Deep Think",
            model=f"Deep Analysis ({len(llm_responses)} AI Models + Web Research)",
            thinking_data=f"Deep Think Analysis completed with {len(llm_responses)} models and {len(web_responses)} web sources in {total_time:.2f}s",
            links=all_links,  # Include all collected links
            metadata={
                'deepthink_mode': True,
                'models_used': [r['model'] for r in llm_responses],
                'web_sources': [r['source'] for r in web_responses],
                'total_analysis_time': total_time,
                'response_count': len(llm_responses) + len(web_responses)
            },
            success=True
        )
    
    def _query_model_for_deepthink(self, model: str, message: str, chat_history: List[Dict]) -> APIResponse:
        """Query a specific model for DeepThink analysis"""
        try:
            enhanced_prompt = f"""Analyze this query comprehensively: "{message}"

Please provide:
1. Your analysis and reasoning
2. Key insights and implications
3. Potential alternative perspectives
4. Practical applications or solutions
5. Any limitations or considerations

Be thorough but concise in your response."""
            
            start_time = time.time()
            response = self._call_llm_model(model, enhanced_prompt, chat_history, ['deepthink'])
            response.response_time = time.time() - start_time
            return response
            
        except Exception as e:
            logger.error(f"Error querying {model} for DeepThink: {e}")
            return APIResponse(
                content="",
                source="DeepThink",
                model=model,
                success=False,
                error=str(e),
                response_time=0.0
            )
    
    def _synthesize_deepthink_responses(
        self, 
        original_query: str, 
        web_responses: List[Dict], 
        llm_responses: List[Dict]
    ) -> str:
        """Synthesize all responses into a comprehensive, unified analysis"""
        
        # Create a cohesive response structure
        content_parts = []
        
        # 1. Executive Summary Header
        content_parts.append(f"🧠⚡ **Deep Think Analysis: {original_query}**")
        content_parts.append("*Comprehensive analysis using multiple AI models and real-time web research*\n")
        
        # 2. Synthesized Main Analysis
        if llm_responses:
            content_parts.append("## 📋 Executive Summary")
            
            # Extract key insights and create a unified explanation
            all_content = []
            for response in llm_responses:
                if response.get('content'):
                    all_content.append(response['content'])
            
            # Create a unified analysis by extracting the best explanations
            unified_analysis = self._create_unified_analysis(original_query, all_content)
            content_parts.append(unified_analysis)
        
        # 3. Web Research Integration (if available)
        if web_responses:
            content_parts.append("\n## 🌐 Web Research Insights")
            
            for web_resp in web_responses:
                if web_resp.get('content'):
                    # Extract key findings from web content
                    web_summary = self._extract_web_key_findings(web_resp['content'])
                    if web_summary:
                        content_parts.append(web_summary)
        
        # 4. Key Insights Summary
        if llm_responses:
            content_parts.append("\n## 💡 Key Insights")
            key_points = self._extract_key_insights_from_models(llm_responses)
            if key_points:
                for i, point in enumerate(key_points[:6], 1):
                    content_parts.append(f"• **{point}**")
        
        # 5. Source Links (if available)
        web_links = []
        for web_resp in web_responses:
            if web_resp.get('links'):
                web_links.extend(web_resp['links'])
        
        if web_links:
            content_parts.append("\n## 🔗 Research Sources")
            unique_links = []
            seen_urls = set()
            for link in web_links:
                if isinstance(link, dict) and link.get('url'):
                    if link['url'] not in seen_urls:
                        unique_links.append(link)
                        seen_urls.add(link['url'])
            
            for i, link in enumerate(unique_links[:5], 1):
                title = link.get('title', f'Source {i}')
                url = link.get('url', '')
                content_parts.append(f"**{i}.** [{title}]({url})")
        
        # 6. Analysis Quality Metrics
        content_parts.append(f"\n## 📊 Analysis Quality Metrics")
        content_parts.append(f"• **Models Analyzed:** {len(llm_responses)} AI models")
        content_parts.append(f"• **Web Sources:** {len(web_responses)} search engines")
        content_parts.append(f"• **Total Data Points:** {len(llm_responses) + len(web_responses)}")
        
        return "\n".join(content_parts)
    
    def _create_unified_analysis(self, query: str, all_content: List[str]) -> str:
        """Create a unified analysis from multiple model responses"""
        if not all_content:
            return "No analysis available."
        
        # Extract the most comprehensive response as the base
        longest_response = max(all_content, key=len)
        
        # Clean and format the primary response
        primary_analysis = self._clean_and_format_response(longest_response)
        
        # Extract additional insights from other responses
        additional_insights = []
        for content in all_content:
            if content != longest_response:
                insights = self._extract_unique_insights(content, primary_analysis)
                additional_insights.extend(insights)
        
        # Combine into a flowing explanation
        result = primary_analysis
        
        if additional_insights:
            # Add the most valuable additional insights
            unique_insights = list(dict.fromkeys(additional_insights))[:3]  # Remove duplicates, take top 3
            for insight in unique_insights:
                if len(insight) > 50 and not any(insight.lower() in result.lower() for _ in [1]):
                    result += f" {insight}"
        
        return result
    
    def _clean_and_format_response(self, content: str) -> str:
        """Clean and format a model response for presentation"""
        # Remove excessive formatting
        cleaned = content.replace('**', '').replace('*', '').strip()
        
        # Take the first substantial paragraph
        paragraphs = [p.strip() for p in cleaned.split('\n\n') if len(p.strip()) > 50]
        
        if paragraphs:
            return paragraphs[0]
        else:
            # Fallback: take first 400 characters
            return cleaned[:400] + "..." if len(cleaned) > 400 else cleaned
    
    def _extract_unique_insights(self, content: str, primary_content: str) -> List[str]:
        """Extract unique insights that aren't already in primary content"""
        insights = []
        
        # Split into sentences and find unique ones
        sentences = [s.strip() for s in content.split('.') if len(s.strip()) > 30]
        
        for sentence in sentences[:3]:  # Check top 3 sentences
            if sentence and len(sentence) > 30:
                # Check if this insight is substantially different from primary content
                if not any(word_set.intersection(set(sentence.lower().split())) > len(sentence.split()) * 0.7 
                          for word_set in [set(primary_content.lower().split())]):
                    insights.append(sentence)
        
        return insights
    
    def _extract_web_key_findings(self, web_content: str) -> str:
        """Extract key findings from web research content"""
        if not web_content:
            return ""
        
        # Look for summary sections or key facts
        lines = web_content.split('\n')
        key_findings = []
        
        for line in lines:
            if any(marker in line.lower() for marker in ['summary', 'key facts', 'definition', 'overview']):
                # Found a summary section, extract next few meaningful lines
                idx = lines.index(line)
                for i in range(idx + 1, min(idx + 4, len(lines))):
                    if lines[i].strip() and len(lines[i].strip()) > 30:
                        key_findings.append(lines[i].strip())
                break
        
        if key_findings:
            return "\n".join(key_findings[:2])  # Return top 2 findings
        else:
            # Fallback: extract first meaningful content
            meaningful_lines = [line.strip() for line in lines if len(line.strip()) > 50 and not line.startswith('🔍')]
            return meaningful_lines[0] if meaningful_lines else ""
    
    def _extract_key_insights_from_models(self, llm_responses: List[Dict]) -> List[str]:
        """Extract key insights from all model responses"""
        insights = []
        
        for response in llm_responses:
            content = response.get('content', '')
            if content:
                # Look for numbered points, bullet points, or key statements
                lines = content.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and (
                        line.startswith(('•', '-', '*')) or
                        any(keyword in line.lower() for keyword in ['key', 'important', 'main', 'primary']) or
                        len(line.split()) > 8  # Substantial statements
                    ):
                        # Clean and add insight
                        clean_line = line.lstrip('•-*').strip()
                        if len(clean_line) > 20 and clean_line not in insights:
                            insights.append(clean_line)
        
        # Remove duplicates and return top insights
        unique_insights = []
        for insight in insights:
            if not any(insight.lower() in existing.lower() for existing in unique_insights):
                unique_insights.append(insight)
        
        return unique_insights[:6]  # Return top 6 insights
    
    def _extract_key_points(self, content: str) -> str:
        """Extract key points from web content"""
        # Simple extraction - take first few sentences that seem informative
        sentences = content.split('.')[:3]
        return '. '.join(sentences) + '.' if sentences else content[:200] + "..."
    
    def _clean_model_response(self, content: str) -> str:
        """Clean and format model response for synthesis"""
        # Remove excessive formatting and clean up
        cleaned = content.replace('**', '').replace('*', '')
        
        # Take first paragraph or up to 250 characters
        paragraphs = cleaned.split('\n\n')
        if paragraphs:
            first_para = paragraphs[0]
            return first_para[:250] + "..." if len(first_para) > 250 else first_para
        
        return cleaned[:250] + "..." if len(cleaned) > 250 else cleaned
    
    def _get_cached_response_with_ttl(self, cache_key: str, ttl: int) -> Optional[APIResponse]:
        """Get cached response if available and not expired with custom TTL"""
        if cache_key in self.response_cache:
            response, timestamp, cache_ttl = self.response_cache[cache_key]
            if (datetime.now() - timestamp).seconds < cache_ttl:
                return response
            else:
                # Remove expired cache
                del self.response_cache[cache_key]
        return None

    def _cache_response_with_ttl(self, cache_key: str, response: APIResponse, ttl: int):
        """Cache response with custom TTL"""
        self.response_cache[cache_key] = (response, datetime.now(), ttl)
        logger.info(f"💾 Cached response with {ttl}s TTL: {cache_key[:50]}...")
        
        # Clean old cache entries periodically
        if len(self.response_cache) > 100:
            self._clean_old_cache_entries()

    def _clean_old_cache_entries(self):
        """Clean expired cache entries"""
        current_time = datetime.now()
        expired_keys = []
        
        for key, (response, timestamp, ttl) in self.response_cache.items():
            if (current_time - timestamp).seconds >= ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.response_cache[key]
        
        if expired_keys:
            logger.info(f"🧹 Cleaned {len(expired_keys)} expired cache entries")

# Create global instance for easy import
api_wrapper = CompanionAPIWrapper()

# Convenience function for backward compatibility
def generate_companion_response(message: str, tools: Optional[List[str]] = None, chat_history: Optional[List[Dict]] = None) -> APIResponse:
    """Generate a response using the Companion API wrapper"""
    return api_wrapper.generate_response(message, tools=tools, chat_history=chat_history)
