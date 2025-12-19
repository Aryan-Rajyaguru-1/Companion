#!/usr/bin/env python3
"""
Test script for Railway deployment
Replace YOUR_RAILWAY_URL with your actual Railway URL
"""

import requests
import json

# ⚠️ REPLACE THIS with your actual Railway URL
RAILWAY_URL = "https://companion-brain-production.up.railway.app"
API_KEY = "2BwdkXsXaOib6t-HGuFPAqhJIxrm3IldQVbv5YtKZe0"

def test_health():
    """Test the health endpoint"""
    print("🏥 Testing health endpoint...")
    try:
        response = requests.get(f"{RAILWAY_URL}/health", timeout=10)
        print(f"✅ Status: {response.status_code}")
        print(f"📄 Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_think():
    """Test the think endpoint"""
    print("\n🧠 Testing think endpoint...")
    try:
        headers = {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        }
        data = {
            "message": "Hello! Are you working on Railway?",
            "use_agi": True
        }
        
        response = requests.post(
            f"{RAILWAY_URL}/api/think",
            headers=headers,
            json=data,
            timeout=30
        )
        
        print(f"✅ Status: {response.status_code}")
        result = response.json()
        print(f"📝 Response: {result.get('response', 'No response')[:200]}...")
        print(f"⚡ Processing time: {result.get('processing_time', 'N/A')}s")
        print(f"🤖 Model: {result.get('model_used', 'N/A')}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_agi_status():
    """Test the AGI status endpoint"""
    print("\n🎯 Testing AGI status endpoint...")
    try:
        headers = {"X-API-Key": API_KEY}
        response = requests.get(
            f"{RAILWAY_URL}/api/agi/status",
            headers=headers,
            timeout=10
        )
        print(f"✅ Status: {response.status_code}")
        print(f"📄 AGI Status: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Railway Deployment Test")
    print("=" * 60)
    print(f"URL: {RAILWAY_URL}")
    print(f"API Key: {API_KEY[:10]}...")
    print("=" * 60)
    
    results = []
    results.append(("Health Check", test_health()))
    results.append(("Think Endpoint", test_think()))
    results.append(("AGI Status", test_agi_status()))
    
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    all_passed = all(result[1] for result in results)
    if all_passed:
        print("\n🎉 All tests passed! Your API is live on Railway!")
    else:
        print("\n⚠️  Some tests failed. Check Railway logs for details.")
        print("Logs: Go to Railway Dashboard → Your Project → Deployments → View Logs")
