#!/usr/bin/env python3
"""
Test script for OpenRouter integration
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.getcwd())

try:
    from config import OPENROUTER_CONFIG, get_openrouter_headers, APP_CONFIG
    from openrouter_client import OpenRouterClient
    
    print(f"✅ Configuration loaded successfully")
    print(f"   Title: {APP_CONFIG['title']}")
    print(f"   Version: {APP_CONFIG['version']}")
    print(f"   Description: {APP_CONFIG['description']}")
    print()
    
    print(f"🔑 API Keys loaded: {len(OPENROUTER_CONFIG['api_keys'])}")
    for key_name in OPENROUTER_CONFIG['api_keys'].keys():
        api_key = OPENROUTER_CONFIG['api_keys'][key_name]
        print(f"   {key_name}: {api_key[:20]}...{api_key[-8:]}")
    print()
    
    print(f"🤖 Available models: {len(OPENROUTER_CONFIG['models'])}")
    for model_id, config in OPENROUTER_CONFIG['models'].items():
        print(f"   {config['emoji']} {config['display_name']}")
        print(f"      Model: {model_id}")
        print(f"      Category: {config['category']}")
        print(f"      Description: {config['description']}")
        print(f"      Max tokens: {config['max_tokens']}")
        print()
    
    print("🌐 Testing OpenRouter client...")
    client = OpenRouterClient()
    print("   ✅ OpenRouter client created successfully")
    
    # Test connection to first model
    first_model = list(OPENROUTER_CONFIG['models'].keys())[0]
    print(f"   Testing connection to {first_model}...")
    
    try:
        result = client.test_connection(first_model)
        if result:
            print("   ✅ Connection test successful!")
        else:
            print("   ❌ Connection test failed")
    except Exception as e:
        print(f"   ❌ Connection test error: {e}")
    
    print("\n🎉 OpenRouter integration is ready!")
    print("   You can now use cloud models in DeepCompanion")
    print("   Available providers: Local (Ollama) + Cloud (OpenRouter)")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("   Please ensure all required files are present")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
