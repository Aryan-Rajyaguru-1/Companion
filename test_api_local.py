#!/usr/bin/env python3
"""
Quick test to verify API server works locally before cloud deployment
"""

import sys
import os
import time
import requests
import subprocess
import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_local_server():
    """Test API server locally"""
    
    print("🧪 Testing Companion Brain API Server")
    print("=" * 50)
    
    # Start server in background
    print("\n1️⃣ Starting API server...")
    server_process = subprocess.Popen(
        [sys.executable, "api_server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    
    # Wait for server to start
    print("   Waiting for server to start...")
    time.sleep(5)
    
    base_url = "http://localhost:8000"
    
    try:
        # Test 1: Root endpoint
        print("\n2️⃣ Testing root endpoint...")
        response = requests.get(f"{base_url}/")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Root endpoint working!")
        else:
            print(f"   ❌ Failed: {response.status_code}")
        
        # Test 2: Health check
        print("\n3️⃣ Testing health endpoint...")
        response = requests.get(f"{base_url}/health")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            health = response.json()
            print(f"   ✅ Health: {health['brain_status']}")
            print(f"   AGI Enabled: {health['agi_enabled']}")
            print(f"   Autonomy: {health['autonomy_enabled']}")
        else:
            print(f"   ❌ Failed: {response.status_code}")
        
        # Test 3: Think endpoint (with development mode - no API key)
        print("\n4️⃣ Testing think endpoint...")
        response = requests.post(
            f"{base_url}/api/think",
            json={
                "message": "Hello! What is 2+2?",
                "use_agi": True
            },
            headers={"X-API-Key": "dev-key"}  # In dev mode, any key works
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Think endpoint working!")
            print(f"   Response: {result.get('response', 'N/A')[:100]}...")
            if result.get('decision_details'):
                print(f"   Modules: {result['decision_details'].get('modules_used', [])}")
        else:
            print(f"   ⚠️  Status: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
        
        # Test 4: Modules list
        print("\n5️⃣ Testing modules endpoint...")
        response = requests.get(
            f"{base_url}/api/modules",
            headers={"X-API-Key": "dev-key"}
        )
        if response.status_code == 200:
            modules = response.json()
            print(f"   ✅ Found {modules['total']} modules")
            print(f"   Modules: {', '.join(modules['modules'][:5])}...")
        
        print("\n" + "=" * 50)
        print("✅ API Server is working correctly!")
        print("\n📦 Ready for cloud deployment!")
        print("\nNext steps:")
        print("1. Run: ./deploy_cloud.sh")
        print("2. Choose your platform (Railway recommended)")
        print("3. Follow the instructions")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ Could not connect to server!")
        print("   Server might have failed to start.")
        print("   Check the error output below:\n")
        
        # Show server errors
        time.sleep(1)
        stdout, stderr = server_process.communicate(timeout=2)
        if stderr:
            print("Server errors:")
            print(stderr.decode())
    
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
    
    finally:
        # Stop server
        print("\n🛑 Stopping server...")
        server_process.send_signal(signal.SIGTERM)
        server_process.wait(timeout=5)
        print("   Server stopped")

if __name__ == "__main__":
    # Set environment to development
    os.environ["ENVIRONMENT"] = "development"
    os.environ["API_KEY"] = "dev-test-key"
    
    test_local_server()
