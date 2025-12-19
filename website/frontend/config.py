#!/usr/bin/env python3
"""
Configuration file for DeepCompanion
Contains API keys and model configurations
"""

import os
from typing import Dict, Any

# OpenRouter API Configuration (Updated with New Free APIs)
OPENROUTER_CONFIG = {
    "base_url": "https://openrouter.ai/api/v1",
    "api_keys": {
        # Load API keys from environment variables for security
        "tongyi_research": os.getenv("OPENROUTER_TONGYI_KEY", ""),
        "deepseek_chat": os.getenv("OPENROUTER_DEEPSEEK_KEY", ""),
        "gpt_oss": os.getenv("OPENROUTER_GPT_OSS_KEY", "")
    },
    "models": {
        # New Working Free Models (November 2025)
        "alibaba/tongyi-deepresearch-30b-a3b:free": {
            "api_key": "tongyi_research",
            "display_name": "Tongyi DeepResearch 30B",
            "description": "Alibaba's advanced research model - excellent for analysis",
            "emoji": "🔬",
            "category": "research",
            "max_tokens": 32768,
            "pricing": {"input": 0.00, "output": 0.00}
        },
        "deepseek/deepseek-chat-v3.1:free": {
            "api_key": "deepseek_chat",
            "display_name": "DeepSeek Chat v3.1",
            "description": "Latest DeepSeek chat model - great for conversations",
            "emoji": "�",
            "category": "general",
            "max_tokens": 32768,
            "pricing": {"input": 0.00, "output": 0.00}
        },
        "openai/gpt-oss-20b:free": {
            "api_key": "gpt_oss",
            "display_name": "GPT-OSS 20B",
            "description": "OpenAI's open-source model - fast and capable",
            "emoji": "�",
            "category": "general",
            "max_tokens": 8192,
            "pricing": {"input": 0.00, "output": 0.00}
        }
    }
}

# Hugging Face API Configuration (Free Inference API)
HUGGINGFACE_CONFIG = {
    "api_key": os.getenv("HUGGINGFACE_API_KEY", ""),
    "base_url": "https://api-inference.huggingface.co/models",
    "timeout": 30,
    "models": {
        "meta-llama/Llama-3.2-3B-Instruct": {
            "display_name": "Llama 3.2 3B Instruct",
            "description": "Meta's efficient instruction model",
            "emoji": "🦙",
            "category": "general",
            "max_tokens": 8192
        },
        "mistralai/Mistral-7B-Instruct-v0.3": {
            "display_name": "Mistral 7B Instruct",
            "description": "Mistral's powerful instruction-tuned model",
            "emoji": "�",
            "category": "general",
            "max_tokens": 32768
        },
        "google/gemma-2-9b-it": {
            "display_name": "Gemma 2 9B",
            "description": "Google's efficient instruction model",
            "emoji": "💎",
            "category": "general",
            "max_tokens": 8192
        },
        "Qwen/Qwen2.5-Coder-32B-Instruct": {
            "display_name": "Qwen2.5 Coder 32B",
            "description": "Specialized coding model",
            "emoji": "💻",
            "category": "coding",
            "max_tokens": 32768
        },
        "microsoft/Phi-3.5-mini-instruct": {
            "display_name": "Phi-3.5 Mini",
            "description": "Microsoft's compact but capable model",
            "emoji": "⚡",
            "category": "general",
            "max_tokens": 8192
        }
    },
    "default_model": "meta-llama/Llama-3.2-3B-Instruct",
    "fallback_models": [
        "meta-llama/Llama-3.2-3B-Instruct",
        "mistralai/Mistral-7B-Instruct-v0.3",
        "google/gemma-2-9b-it",
        "microsoft/Phi-3.5-mini-instruct"
    ],
    "rate_limit": {
        "requests_per_minute": 30,
        "requests_per_day": 1000  # Free tier limit
    }
}

# Application settings
APP_CONFIG = {
    "title": "DeepCompanion v3.0 - Local & Cloud AI Chat",
    "version": "3.0.0",
    "description": "Modern GUI for local Ollama and cloud OpenRouter models",
    "author": "DeepCompanion Team",
    "local_models_enabled": True,
    "cloud_models_enabled": True,
    "default_provider": "local",  # "local" or "cloud"
    "ollama_url": "http://localhost:11434"
}

# Groq API Configuration (Ultra-Fast Inference)
GROQ_CONFIG = {
    "api_key": os.getenv("GROQ_API_KEY", ""),
    "base_url": "https://api.groq.com/openai/v1",
    "timeout": 30,
    "models": {
        "llama-3.3-70b-versatile": {
            "display_name": "Llama 3.3 70B Versatile",
            "description": "Latest Llama model, extremely fast and capable",
            "emoji": "⚡",
            "category": "general",
            "max_tokens": 32768,
            "speed": "ultra-fast"
        },
        "llama-3.1-8b-instant": {
            "display_name": "Llama 3.1 8B Instant",
            "description": "Ultra-fast small model for quick responses",
            "emoji": "🚀",
            "category": "general",
            "max_tokens": 8192,
            "speed": "instant"
        },
        "mixtral-8x7b-32768": {
            "display_name": "Mixtral 8x7B",
            "description": "Powerful mixture-of-experts model",
            "emoji": "🔥",
            "category": "reasoning",
            "max_tokens": 32768,
            "speed": "very-fast"
        },
        "llama3-70b-8192": {
            "display_name": "Llama 3 70B",
            "description": "Large context window, great for complex tasks",
            "emoji": "🦙",
            "category": "general",
            "max_tokens": 8192,
            "speed": "fast"
        },
        "llama3-8b-8192": {
            "display_name": "Llama 3 8B",
            "description": "Efficient small model with good performance",
            "emoji": "💨",
            "category": "general",
            "max_tokens": 8192,
            "speed": "very-fast"
        },
        "gemma2-9b-it": {
            "display_name": "Gemma 2 9B",
            "description": "Google's efficient instruction-tuned model",
            "emoji": "💎",
            "category": "general",
            "max_tokens": 8192,
            "speed": "fast"
        }
    },
    "default_model": "llama-3.3-70b-versatile",
    "fallback_models": [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
        "llama3-70b-8192"
    ],
    "rate_limit": {
        "requests_per_minute": 30,
        "requests_per_day": 14400
    }
}

# Ollama Local LLM Configuration
OLLAMA_CONFIG = {
    "base_url": "http://localhost:11434",
    "api_endpoint": "/api/generate",
    "chat_endpoint": "/api/chat",
    "timeout": 60,  # seconds
    "models": {
        "llama3.2:3b": {
            "display_name": "Llama 3.2 3B",
            "description": "Fast and efficient local model",
            "emoji": "🦙",
            "category": "general",
            "context_length": 8192
        },
        "codegemma:2b": {
            "display_name": "CodeGemma 2B",
            "description": "Lightweight coding specialist",
            "emoji": "💻",
            "category": "coding",
            "context_length": 8192
        },
        "codeqwen:7b": {
            "display_name": "CodeQwen 7B",
            "description": "Advanced coding and reasoning",
            "emoji": "🔧",
            "category": "coding",
            "context_length": 32768
        },
        "deepseek-r1:1.5b": {
            "display_name": "DeepSeek R1 1.5B",
            "description": "Reasoning and analysis focused",
            "emoji": "🧠",
            "category": "reasoning",
            "context_length": 8192
        }
    },
    "default_model": "llama3.2:3b",
    "fallback_models": [
        "llama3.2:3b",
        "deepseek-r1:1.5b",
        "codeqwen:7b",
        "codegemma:2b"
    ]
}

def get_openrouter_headers(model_name: str) -> Dict[str, str]:
    """Get headers for OpenRouter API requests"""
    if model_name not in OPENROUTER_CONFIG["models"]:
        raise ValueError(f"Model {model_name} not configured")
    
    model_config = OPENROUTER_CONFIG["models"][model_name]
    api_key_name = model_config["api_key"]
    api_key = OPENROUTER_CONFIG["api_keys"][api_key_name]
    
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://deepcompanion.ai",  # Your site URL
        "X-Title": "DeepCompanion v3.0"
    }

def get_model_config(model_name: str) -> Dict[str, Any]:
    """Get configuration for a specific model"""
    return OPENROUTER_CONFIG["models"].get(model_name, {})

def list_available_models() -> Dict[str, Dict[str, Any]]:
    """List all available OpenRouter models"""
    return OPENROUTER_CONFIG["models"]
