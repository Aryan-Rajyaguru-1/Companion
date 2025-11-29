#!/usr/bin/env python3
"""
Test script to verify OpenRouter API keys work correctly
"""

import requests
import json
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OPENROUTER_CONFIG, get_openrouter_headers, get_model_config

def test_api_key(model_name, test_message="Hello, respond with just 'API WORKING'"):
    """Test a specific API key with a simple request"""
    try:
        print(f"\n🧪 Testing {model_name}...")
        
        # Get model config
        model_config = get_model_config(model_name)
        if not model_config:
            print(f"❌ Model {model_name} not configured")
            return False
        
        # Get headers
        headers = get_openrouter_headers(model_name)
        api_key = headers['Authorization'].split(' ')[1]
        print(f"🔑 API Key: {api_key[:20]}...{api_key[-10:]}")
        
        # Prepare simple request
        payload = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": test_message}
            ],
            "max_tokens": 50,
            "temperature": 0.1
        }
        
        print(f"📡 Making request to OpenRouter...")
        
        # Make request
        response = requests.post(
            f"{OPENROUTER_CONFIG['base_url']}/chat/completions",
            headers=headers,
            json=payload,
            timeout=15
        )
        
        print(f"📊 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if 'choices' in data and len(data['choices']) > 0:
                content = data['choices'][0]['message']['content']
                print(f"✅ SUCCESS: {content[:100]}...")
                return True
            else:
                print(f"⚠️  No choices in response: {data}")
                return False
        else:
            print(f"❌ FAILED: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"💥 ERROR: {str(e)}")
        return False

def main():
    """Test all available API keys"""
    print("🚀 Testing OpenRouter API Keys for Companion")
    print("=" * 50)
    
    # Test models in order of preference
    models_to_test = [
        "google/gemini-2.5-flash",
        "openai/gpt-4o-2024-08-06",
        "deepseek/deepseek-r1-0528",
        "mistralai/devstral-medium",
        "openai/gpt-4.1",
        "perplexity/sonar-deep-research",
        "anthropic/claude-3.7-sonnet:beta"
    ]
    
    working_models = []
    failed_models = []
    
    for model in models_to_test:
        if test_api_key(model):
            working_models.append(model)
        else:
            failed_models.append(model)
    
    print("\n" + "=" * 50)
    print("📋 SUMMARY:")
    print(f"✅ Working Models ({len(working_models)}): {working_models}")
    print(f"❌ Failed Models ({len(failed_models)}): {failed_models}")
    
    if working_models:
        print(f"\n🎯 Recommended primary model: {working_models[0]}")
        return working_models[0]
    else:
        print("\n🔥 ALL API KEYS FAILED - Need to check keys or try different approach")
        return None

if __name__ == "__main__":
    main()
