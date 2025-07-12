#!/usr/bin/env python3
"""
Configuration file for DeepCompanion
Contains API keys and model configurations
"""

import os
from typing import Dict, Any

# OpenRouter API Configuration
OPENROUTER_CONFIG = {
    "base_url": "https://openrouter.ai/api/v1",
    "api_keys": {
        "primary": "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",
        "secondary": "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", 
        "tertiary": "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",
        "quaternary": "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",
        "quinary": "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",
        "senary": "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"
    },
    "models": {
        "deepseek/deepseek-r1-0528": {
            "api_key": "primary",
            "display_name": "DeepSeek R1 (Cloud)",
            "description": "Advanced reasoning and step-by-step analysis",
            "emoji": "🧠",
            "category": "reasoning",
            "max_tokens": 32768,
            "pricing": {"input": 0.14, "output": 0.28}
        },
        "google/gemini-2.5-flash": {
            "api_key": "secondary", 
            "display_name": "Gemini 2.5 Flash",
            "description": "Google's fast multimodal AI for quick responses",
            "emoji": "⚡",
            "category": "general",
            "max_tokens": 8192,
            "pricing": {"input": 0.075, "output": 0.30}
        },
        "openai/gpt-4o-2024-08-06": {
            "api_key": "tertiary",
            "display_name": "GPT-4o",
            "description": "OpenAI's most advanced multimodal model",
            "emoji": "🤖",
            "category": "general", 
            "max_tokens": 16384,
            "pricing": {"input": 2.50, "output": 10.00}
        },
        "mistralai/devstral-medium": {
            "api_key": "quaternary",
            "display_name": "Mistral Devstral",
            "description": "Specialized for code generation and development",
            "emoji": "💻",
            "category": "coding",
            "max_tokens": 32768,
            "pricing": {"input": 0.14, "output": 0.14}
        },
        "openai/gpt-4.1": {
            "api_key": "quinary",
            "display_name": "GPT-4.1",
            "description": "Enhanced GPT-4 with improved capabilities",
            "emoji": "🚀",
            "category": "general",
            "max_tokens": 8192,
            "pricing": {"input": 5.00, "output": 15.00}
        },
        "perplexity/sonar-deep-research": {
            "api_key": "senary",
            "display_name": "Perplexity Sonar",
            "description": "Deep research with real-time web search",
            "emoji": "🔍",
            "category": "research",
            "max_tokens": 4096,
            "pricing": {"input": 5.00, "output": 5.00}
        }
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
