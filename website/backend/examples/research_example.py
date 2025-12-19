#!/usr/bin/env python3
"""
Example: Research Assistant using Companion BaaS
================================================

This example shows how to build a research tool with web search.
Same brain, different purpose!
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from companion_baas.sdk import BrainClient

def main():
    """Research assistant example"""
    
    print("=" * 60)
    print("🔬 Research Assistant powered by Companion BaaS")
    print("=" * 60)
    print("Type 'quit' to exit\n")
    
    # Initialize the brain for research
    client = BrainClient(app_type="research")
    user_id = "researcher_456"
    
    print("🤖 I'm your research assistant! I can search the web and analyze information.\n")
    
    while True:
        try:
            user_input = input("Researcher: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == 'quit':
                print("\n👋 Happy researching!")
                break
            
            print("🔍 Researching...", end="\r")
            
            # Brain automatically uses web search for research!
            response = client.chat(
                message=user_input,
                user_id=user_id,
                tools=['web', 'deepsearch']  # Enable research tools
            )
            
            if response['success']:
                print(" " * 20, end="\r")
                print(f"Assistant: {response['response']}\n")
                
                # Show sources if available
                if response['metadata'].get('links'):
                    print("📚 Sources:")
                    for link in response['metadata']['links'][:3]:
                        print(f"   • {link['title']}: {link['url']}")
                    print()
            else:
                print(f"❌ Error: {response.get('error')}\n")
                
        except KeyboardInterrupt:
            print("\n\n👋 Happy researching!")
            break

if __name__ == "__main__":
    main()
