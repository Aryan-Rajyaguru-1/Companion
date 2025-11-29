"""
Basic Chatbot Example - Traditional BrainClient
100% compatible with existing code - no changes needed!
"""

from companion_baas.sdk import BrainClient

def main():
    # Create traditional brain client
    client = BrainClient(app_type="chatbot")
    
    print("=== Traditional Chatbot ===")
    print("Type 'quit' to exit\n")
    
    while True:
        user_input = input("You: ")
        
        if user_input.lower() in ['quit', 'exit']:
            break
        
        # Simple ask - works exactly as before
        response = client.ask(user_input)
        print(f"Bot: {response}\n")

if __name__ == "__main__":
    main()
