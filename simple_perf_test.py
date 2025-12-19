#!/usr/bin/env python3
"""
Simple Performance Test for Companion AI
========================================

Quick performance testing script
"""

import time
import requests
import json
import statistics

def test_api_performance():
    """Test basic API performance"""
    base_url = "http://localhost:5000/api"

    print("🚀 Testing Companion AI Performance")
    print("=" * 40)

    # Test 1: Create conversation
    print("1️⃣ Creating conversation...")
    try:
        response = requests.post(f"{base_url}/conversations", json={
            "title": "Performance Test",
            "user_id": "perf_test"
        })
        if response.status_code in [200, 201]:
            conv_data = response.json()
            conversation_id = conv_data['id']
            print(f"✅ Conversation created: {conversation_id}")
        else:
            print(f"❌ Failed to create conversation: {response.status_code}")
            print(f"Response: {response.text}")
            return
    except Exception as e:
        print(f"❌ Error creating conversation: {e}")
        return

    # Test 2: Send messages and measure response time
    print("\n2️⃣ Testing message response times...")
    messages = [
        "Hello!",
        "What is AI?",
        "Tell me a joke",
        "How does machine learning work?",
        "What is the meaning of life?"
    ]

    response_times = []

    for i, message in enumerate(messages):
        try:
            start_time = time.time()
            response = requests.post(
                f"{base_url}/conversations/{conversation_id}/messages",
                json={"message": message, "user_id": "perf_test"},
                timeout=30
            )
            end_time = time.time()

            if response.status_code == 200:
                response_time = end_time - start_time
                response_times.append(response_time)
                print(".2f")
                # Get AI response
                data = response.json()
                if 'ai_response' in data:
                    print(f"   🤖 AI: {data['ai_response'][:50]}...")
            else:
                print(f"❌ Message {i+1} failed: {response.status_code}")

        except Exception as e:
            print(f"❌ Message {i+1} error: {e}")

    # Results
    print("\n📊 PERFORMANCE RESULTS")
    print("=" * 40)

    if response_times:
        print("🚀 API Response Times:")
        print(".2f")
        print(".2f")
        print(".2f")
        print(".2f")

        # Performance grade
        avg_time = statistics.mean(response_times)
        if avg_time < 2.0:
            grade = "A (Excellent)"
        elif avg_time < 5.0:
            grade = "B (Good)"
        elif avg_time < 10.0:
            grade = "C (Fair)"
        else:
            grade = "D (Needs improvement)"

        print(f"🎯 Performance Grade: {grade}")

    print(f"✅ Successful Requests: {len(response_times)}/{len(messages)}")
    print("\n🎉 Performance test complete!")

if __name__ == "__main__":
    test_api_performance()