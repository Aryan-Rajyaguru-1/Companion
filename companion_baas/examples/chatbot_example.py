#!/usr/bin/env python3
"""
Example: Chatbot Application using Companion BaaS
==================================================

This example shows how to build a simple chatbot using the Brain framework.
Notice how we don't need to worry about AI models, prompts, or API keys!
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from companion_baas.sdk import BrainClient

def main():
    """Simple chatbot example"""
    
    print("=" * 60)
    print("🤖 Chatbot powered by Companion BaaS")
    print("=" * 60)
    print("Type 'quit' to exit, 'clear' to clear history, 'stats' for stats\n")
    
    # Initialize the brain for chatbot
    client = BrainClient(app_type="chatbot")
    user_id = "demo_user"
    
    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == 'quit':
                print("\n👋 Goodbye!")
                break
            
            if user_input.lower() == 'clear':
                client.clear_history(user_id=user_id)
                print("✅ Conversation cleared!\n")
                continue
            
            if user_input.lower() == 'stats':
                stats = client.get_stats()
                print(f"\n📊 Brain Stats:")
                print(f"   Total Requests: {stats['total_requests']}")
                print(f"   Success Rate: {stats['success_rate']:.1f}%")
                print(f"   Avg Response Time: {stats['average_response_time']:.2f}s")
                print(f"   Cached Responses: {stats['cached_responses']}")
                print(f"   Models Used: {stats['models_used']}")
                print()
                continue
            
            # Send message to brain
            print("🧠 Thinking...", end="\r")
            
            response = client.chat(
                message=user_input,
                user_id=user_id
            )
            
            if response['success']:
                # Display response
                print(" " * 20, end="\r")  # Clear "Thinking..."
                print(f"Bot: {response['response']}\n")
                
                # Show metadata
                metadata = response['metadata']
                print(f"   ℹ️  Model: {metadata.get('model', 'N/A')} | "
                      f"Time: {metadata.get('response_time', 0):.2f}s | "
                      f"Source: {metadata.get('source', 'N/A')}")
                print()
            else:
                print(f"❌ Error: {response.get('error', 'Unknown error')}\n")
                
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}\n")

if __name__ == "__main__":
    main()
