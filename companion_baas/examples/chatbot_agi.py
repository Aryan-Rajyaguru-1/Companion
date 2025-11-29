"""
AGI Chatbot Example - One Line Upgrade!
Just change the import to get full AGI features
"""

from companion_baas import Brain

def main():
    # Create AGI brain - same API, AGI features included!
    brain = Brain(app_type="chatbot", enable_agi=True)
    
    print("=== AGI Chatbot ===")
    print(f"🧠 Personality: {brain._personality_engine.personality_id}")
    print("\nCommands:")
    print("  /personality - Show personality details")
    print("  /stats - Show learning statistics")
    print("  quit - Exit\n")
    
    while True:
        user_input = input("You: ")
        
        if user_input.lower() in ['quit', 'exit']:
            break
        
        if user_input == "/personality":
            p = brain.get_personality()
            print(f"\n🎭 Personality ID: {p['personality_id']}")
            print(f"😊 Current Emotion: {p['emotion']}")
            print(f"⭐ Top Traits: {', '.join(p['dominant_traits'][:3])}")
            print(f"📊 Trait Scores:")
            for trait, score in p['traits'].items():
                print(f"   {trait}: {score:.2f}")
            print()
            continue
        
        if user_input == "/stats":
            stats = brain.get_learning_stats()
            print(f"\n📚 Learning Statistics:")
            print(f"   Episodes: {stats['episodes']}")
            print(f"   Concepts: {stats['concepts']}")
            print(f"   Skills: {stats['skills']}")
            print(f"   Strategies: {stats['strategies']}")
            print(f"   Success Rate: {stats['success_rate']:.2%}")
            print()
            continue
        
        # Enhanced thinking with AGI
        result = brain.think(user_input, mode="auto")
        print(f"Bot: {result['response']}\n")

if __name__ == "__main__":
    main()
