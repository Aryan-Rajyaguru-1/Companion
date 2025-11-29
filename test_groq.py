#!/usr/bin/env python3
"""Quick test of Groq API integration"""

import sys
sys.path.append('website')

from api_wrapper import call_groq_api

# Test Groq API
print("🧪 Testing Groq API integration...\n")

response = call_groq_api("Say hello in one sentence", chat_history=[], model="llama-3.1-8b-instant")

if response and response.success:
    print(f"✅ SUCCESS!")
    print(f"📝 Response: {response.content}")
    print(f"⚡ Source: {response.source}")
    print(f"⏱️  Time: {response.response_time:.2f}s")
    print(f"🎯 Metadata: {response.metadata}")
else:
    print("❌ FAILED: No response from Groq API")
