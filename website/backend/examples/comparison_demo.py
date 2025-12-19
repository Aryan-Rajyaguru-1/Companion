"""
Side-by-Side Comparison: Traditional vs AGI
Shows how both can coexist in the same application
"""

from companion_baas.sdk import BrainClient
from companion_baas import Brain

def main():
    print("=== Initializing Both Brains ===\n")
    
    # Traditional brain
    traditional = BrainClient(app_type="chatbot")
    print("✅ Traditional BrainClient initialized")
    
    # AGI brain
    agi = Brain(app_type="chatbot", enable_agi=True)
    print(f"✅ AGI Brain initialized (personality: {agi._personality_engine.personality_id})")
    
    print("\n" + "="*60)
    print("Both brains running side-by-side!")
    print("="*60)
    
    # Test questions
    questions = [
        "What is artificial intelligence?",
        "How do neural networks work?",
        "Explain quantum computing"
    ]
    
    for i, question in enumerate(questions, 1):
        print(f"\n{'='*60}")
        print(f"Question {i}: {question}")
        print('='*60)
        
        # Traditional response
        print("\n📱 Traditional BrainClient:")
        trad_response = traditional.ask(question)
        print(f"   {trad_response}")
        
        # AGI response with personality
        print("\n🧠 AGI Brain:")
        agi_result = agi.think(question, mode="auto")
        print(f"   {agi_result['response']}")
        
        # Show AGI extras
        personality = agi.get_personality()
        print(f"\n   💫 Personality: {personality['emotion']}")
        print(f"   🎯 Dominant traits: {', '.join(personality['dominant_traits'][:2])}")
    
    # Show final stats
    print("\n" + "="*60)
    print("Final Statistics")
    print("="*60)
    
    print("\n📱 Traditional BrainClient:")
    print("   - Lightweight")
    print("   - No learning overhead")
    print("   - Pure API responses")
    
    print("\n🧠 AGI Brain:")
    stats = agi.get_learning_stats()
    print(f"   - Learned from {stats['episodes']} episodes")
    print(f"   - Acquired {stats['concepts']} concepts")
    print(f"   - Developed unique personality")
    print(f"   - Neural reasoning enabled")
    
    print("\n✅ Both approaches work perfectly together!")

if __name__ == "__main__":
    main()
