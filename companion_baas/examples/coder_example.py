#!/usr/bin/env python3
"""
Example: Code Assistant using Companion BaaS
=============================================

This example shows how to build a coding assistant.
Same brain, different app!
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from companion_baas.sdk import BrainClient

def main():
    """Code assistant example"""
    
    print("=" * 60)
    print("💻 Code Assistant powered by Companion BaaS")
    print("=" * 60)
    print("Type 'quit' to exit\n")
    
    # Initialize the brain for coding
    client = BrainClient(app_type="coder")
    user_id = "developer_123"
    
    print("🤖 I'm your coding assistant! Ask me anything about programming.\n")
    
    while True:
        try:
            user_input = input("Developer: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == 'quit':
                print("\n👋 Happy coding!")
                break
            
            print("🧠 Processing...", end="\r")
            
            # Brain automatically uses code-optimized models!
            response = client.chat(
                message=user_input,
                user_id=user_id,
                tools=['code']  # Enable code tool
            )
            
            if response['success']:
                print(" " * 20, end="\r")
                print(f"Assistant: {response['response']}\n")
            else:
                print(f"❌ Error: {response.get('error')}\n")
                
        except KeyboardInterrupt:
            print("\n\n👋 Happy coding!")
            break

if __name__ == "__main__":
    main()
