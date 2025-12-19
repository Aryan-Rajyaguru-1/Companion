#!/usr/bin/env python3
"""
Example: Using your Companion Brain API from anywhere!
Replace the URL and API_KEY with your Railway deployment details.
"""

from client_library import CompanionBrainCloudClient

# ⚠️ REPLACE THESE with your Railway deployment details
RAILWAY_URL = "https://companion-brain-production.up.railway.app"
API_KEY = "2BwdkXsXaOib6t-HGuFPAqhJIxrm3IldQVbv5YtKZe0"

def main():
    print("🧠 Companion Brain Cloud Client Example")
    print("=" * 60)
    
    # Initialize the client
    brain = CompanionBrainCloudClient(
        base_url=RAILWAY_URL,
        api_key=API_KEY
    )
    
    print("✅ Client initialized!")
    print(f"🌐 Connected to: {RAILWAY_URL}")
    print("=" * 60)
    
    # Check health
    print("\n1️⃣ Checking brain health...")
    health = brain.health()
    print(f"   Status: {health.get('status', 'unknown')}")
    print(f"   AGI Active: {health.get('agi_active', False)}")
    print(f"   Total Modules: {health.get('total_modules', 0)}")
    
    # Ask a question
    print("\n2️⃣ Asking the brain a question...")
    question = "What is artificial general intelligence?"
    print(f"   Question: {question}")
    
    result = brain.think(question, use_agi=True)
    print(f"\n   🤖 Response:")
    print(f"   {result.response[:300]}...")
    print(f"\n   ⚡ Processing Time: {result.processing_time:.2f}s")
    print(f"   📊 Model Used: {result.model_used}")
    
    # Get AGI status
    print("\n3️⃣ Getting AGI status...")
    agi_status = brain.agi_status()
    print(f"   Enabled: {agi_status.get('enabled', False)}")
    print(f"   Modules Active: {agi_status.get('modules_active', 0)}")
    
    # Get stats
    print("\n4️⃣ Getting brain statistics...")
    stats = brain.stats()
    print(f"   Total Requests: {stats.get('total_requests', 0)}")
    print(f"   Average Response Time: {stats.get('avg_response_time', 0):.2f}s")
    
    print("\n" + "=" * 60)
    print("🎉 Success! Your brain is accessible from anywhere!")
    print("=" * 60)
    
    print("\n💡 What you can do now:")
    print("   • Access your AGI brain from any Python script")
    print("   • Build apps that use your brain's intelligence")
    print("   • Share the API with your team")
    print("   • No need to import local modules anymore!")
    print("\n📚 Check client_library.py for more features:")
    print("   • Async support (AsyncCompanionBrainCloudClient)")
    print("   • Streaming responses")
    print("   • Conversation management")
    print("   • Module control")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\n🔍 Troubleshooting:")
        print("   1. Make sure RAILWAY_URL is correct")
        print("   2. Verify API_KEY matches Railway environment variable")
        print("   3. Check Railway logs for errors")
        print("   4. Ensure your Railway app is running")
