"""
Advanced AGI Chatbot with Autonomous Learning
Demonstrates full AGI capabilities with self-improvement
"""

from companion_baas import Brain
import json

def main():
    # Create AGI brain with all features
    brain = Brain(
        app_type="chatbot",
        enable_agi=True,
        enable_autonomy=False  # Start safe, enable later if needed
    )
    
    print("=== Advanced AGI Chatbot ===")
    print(f"🧠 Personality: {brain._personality_engine.personality_id}")
    print("\nCommands:")
    print("  /personality - Show personality")
    print("  /stats - Learning statistics")
    print("  /agi - AGI system status")
    print("  /teach <concept> - Teach new concept")
    print("  /recall <query> - Recall memories")
    print("  /synthesize - Creative idea synthesis")
    print("  /autonomy - Toggle autonomous mode")
    print("  quit - Exit\n")
    
    while True:
        user_input = input("You: ")
        
        if user_input.lower() in ['quit', 'exit']:
            break
        
        # Personality info
        if user_input == "/personality":
            p = brain.get_personality()
            print(f"\n🎭 Personality Profile:")
            print(f"   ID: {p['personality_id']}")
            print(f"   Emotion: {p['emotion']}")
            print(f"   Dominant Traits: {', '.join(p['dominant_traits'])}")
            print(f"\n📊 All Traits:")
            for trait, score in sorted(p['traits'].items(), key=lambda x: x[1], reverse=True):
                bar = "█" * int(score * 20)
                print(f"   {trait:15s} [{bar:<20s}] {score:.2f}")
            print()
            continue
        
        # Learning stats
        if user_input == "/stats":
            stats = brain.get_learning_stats()
            print(f"\n📚 Learning System:")
            print(f"   📖 Episodic Memory: {stats['episodes']} episodes")
            print(f"   🧠 Semantic Memory: {stats['concepts']} concepts")
            print(f"   🎯 Procedural Memory: {stats['skills']} skills")
            print(f"   ⭐ Mastered Skills: {stats['mastered_skills']}")
            print(f"   🎲 Meta-Learning: {stats['strategies']} strategies")
            print(f"   ✅ Success Rate: {stats['success_rate']:.2%}")
            print()
            continue
        
        # AGI status
        if user_input == "/agi":
            status = brain.get_agi_status()
            print(f"\n🤖 AGI System Status:")
            print(f"   AGI Enabled: {status['agi_enabled']}")
            print(f"   Autonomy: {status['autonomous_stats']['enabled']}")
            print(f"\n🧩 Components:")
            for component, enabled in status['components'].items():
                emoji = "✅" if enabled else "❌"
                print(f"   {emoji} {component}")
            print()
            continue
        
        # Teach concept
        if user_input.startswith("/teach"):
            parts = user_input.split(maxsplit=1)
            if len(parts) < 2:
                print("Usage: /teach <concept_name>\n")
                continue
            
            concept = parts[1]
            print(f"Teaching concept '{concept}'...")
            print("Enter examples (empty line to finish):")
            examples = []
            while True:
                example = input("  > ")
                if not example:
                    break
                examples.append(example)
            
            if examples:
                brain.teach_concept(concept, examples)
                print(f"✅ Taught {len(examples)} examples for '{concept}'\n")
            else:
                print("No examples provided\n")
            continue
        
        # Recall memories
        if user_input.startswith("/recall"):
            parts = user_input.split(maxsplit=1)
            query = parts[1] if len(parts) > 1 else ""
            
            if not query:
                print("Usage: /recall <query>\n")
                continue
            
            memories = brain.recall_memories(query, limit=5)
            print(f"\n🔍 Recalled {len(memories)} memories:")
            for i, memory in enumerate(memories, 1):
                print(f"   {i}. {memory}")
            print()
            continue
        
        # Creative synthesis
        if user_input == "/synthesize":
            print("Enter ideas to synthesize (empty line to finish):")
            ideas = []
            while True:
                idea = input("  > ")
                if not idea:
                    break
                ideas.append(idea)
            
            if len(ideas) >= 2:
                goal = input("Goal: ")
                result = brain.synthesize_ideas(ideas, goal)
                print(f"\n💡 Synthesis Result: {result}\n")
            else:
                print("Need at least 2 ideas\n")
            continue
        
        # Toggle autonomy
        if user_input == "/autonomy":
            auto_stats = brain.get_autonomous_stats()
            if auto_stats['enabled']:
                brain.disable_autonomy()
                print("⚠️ Autonomous mode DISABLED (safe)\n")
            else:
                confirm = input("⚠️ Enable autonomous mode? (allows self-modification) [y/N]: ")
                if confirm.lower() == 'y':
                    brain.enable_autonomy(auto_approve_low_risk=True)
                    print("🤖 Autonomous mode ENABLED\n")
                else:
                    print("Autonomous mode remains disabled\n")
            continue
        
        # Enhanced AGI thinking
        result = brain.think(user_input, mode="auto")
        print(f"Bot: {result['response']}\n")

if __name__ == "__main__":
    main()
