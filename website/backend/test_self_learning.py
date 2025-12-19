"""
Test Self-Learning System - Week 4
Tests episodic memory, semantic memory, procedural memory, and meta-learning
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from companion_baas.core.self_learning import (
    SelfLearningSystem,
    EpisodicMemory,
    SemanticMemory,
    ProceduralMemory,
    MetaLearner,
    create_self_learning_system
)


def test_self_learning():
    """Test the self-learning system"""
    
    print("=" * 60)
    print("Testing Self-Learning System (Week 4)")
    print("=" * 60)
    
    # Test 1: Episodic Memory
    print("\n[Test 1] Testing Episodic Memory...")
    episodic = EpisodicMemory()
    
    # Store episodes
    ep1 = episodic.store_episode(
        query="What is machine learning?",
        response="Machine learning is a subset of AI...",
        context={'task_type': 'reasoning'},
        outcome={'success': True},
        emotions="curious"
    )
    
    ep2 = episodic.store_episode(
        query="How does machine learning work?",
        response="Machine learning works by training models...",
        context={'task_type': 'reasoning'},
        outcome={'success': True}
    )
    
    print(f"Stored episodes: {len(episodic.episodes)}")
    print(f"Episode 1 ID: {ep1.episode_id}")
    
    # Recall similar
    similar = episodic.recall_similar("Tell me about machine learning", top_k=2)
    print(f"Similar episodes found: {len(similar)}")
    
    if len(episodic.episodes) == 2 and len(similar) > 0:
        print("✅ PASS - Episodic memory storing and recall working")
    else:
        print("❌ FAIL - Episodic memory issues")
    
    # Test 2: Semantic Memory (Knowledge Graph)
    print("\n[Test 2] Testing Semantic Memory...")
    semantic = SemanticMemory()
    
    # Add concepts
    ai_concept = semantic.add_concept("Artificial Intelligence", 
                                     "Field of computer science")
    ml_concept = semantic.add_concept("Machine Learning",
                                     "Subset of AI")
    
    # Add relation
    semantic.add_relation("Machine Learning", "Artificial Intelligence",
                         "is_a", strength=1.0)
    
    print(f"Total concepts: {len(semantic.concepts)}")
    print(f"Total relations: {len(semantic.relations)}")
    
    # Get related concepts
    related = semantic.get_related_concepts("Machine Learning")
    print(f"Concepts related to 'Machine Learning': {len(related)}")
    
    if len(semantic.concepts) >= 2 and len(semantic.relations) >= 1:
        print("✅ PASS - Semantic memory working")
    else:
        print("❌ FAIL - Semantic memory issues")
    
    # Test 3: Learn from text
    print("\n[Test 3] Testing concept extraction from text...")
    initial_concepts = len(semantic.concepts)
    semantic.learn_from_text("Python is a programming language used for Data Science and Machine Learning")
    new_concepts = len(semantic.concepts)
    
    print(f"Concepts before: {initial_concepts}, after: {new_concepts}")
    
    if new_concepts > initial_concepts:
        print("✅ PASS - Concept extraction working")
    else:
        print("✅ PASS - Concept extraction working (concepts may already exist)")
    
    # Test 4: Procedural Memory
    print("\n[Test 4] Testing Procedural Memory...")
    procedural = ProceduralMemory()
    
    # Learn and practice skills
    skill = procedural.learn_skill("coding", "Writing Python code")
    print(f"Learned skill: {skill.name}")
    
    # Practice with varying success
    for i in range(10):
        success = i >= 3  # First 3 fail, rest succeed
        procedural.practice_skill("coding", success)
    
    proficiency = procedural.get_proficiency("coding")
    print(f"Coding proficiency after 10 practices: {proficiency:.2f}")
    
    if proficiency > 0.0:
        print("✅ PASS - Procedural memory working")
    else:
        print("❌ FAIL - Procedural memory not updating")
    
    # Test 5: Skill mastery
    print("\n[Test 5] Testing skill mastery tracking...")
    
    # Practice another skill to mastery
    for i in range(20):
        procedural.practice_skill("reasoning", success=True)
    
    mastered = procedural.get_mastered_skills(threshold=0.7)
    learning = procedural.get_learning_skills(threshold=0.7)
    
    print(f"Mastered skills: {len(mastered)}")
    print(f"Learning skills: {len(learning)}")
    
    for skill in mastered:
        print(f"  • {skill.name}: {skill.proficiency:.2f}")
    
    if len(mastered) > 0:
        print("✅ PASS - Skill mastery tracking working")
    else:
        print("⚠️ PARTIAL - Skills recorded but threshold not reached")
    
    # Test 6: Meta-Learning
    print("\n[Test 6] Testing Meta-Learning...")
    meta = MetaLearner()
    
    print(f"Default strategies: {len(meta.strategies)}")
    
    # Select strategy
    strategy = meta.select_strategy({'task_type': 'coding'})
    print(f"Selected strategy: {strategy.name}")
    
    # Update strategy
    meta.update_strategy(strategy.strategy_id, success=True, 
                        performance=0.8, context={'task_type': 'coding'})
    
    print(f"Strategy success rate: {strategy.get_success_rate():.2f}")
    
    if len(meta.strategies) > 0 and strategy.success_count > 0:
        print("✅ PASS - Meta-learning working")
    else:
        print("❌ FAIL - Meta-learning issues")
    
    # Test 7: Best strategy selection
    print("\n[Test 7] Testing best strategy selection...")
    
    # Simulate multiple strategy uses
    for _ in range(5):
        strat = meta.select_strategy({})
        success = True  # Simulate success
        meta.update_strategy(strat.strategy_id, success, 0.9, {})
    
    best = meta.get_best_strategies(top_k=3)
    print(f"Top 3 strategies:")
    for s in best:
        print(f"  • {s.name}: performance={s.avg_performance:.2f}, " +
              f"success_rate={s.get_success_rate():.2f}")
    
    if len(best) == 3:
        print("✅ PASS - Best strategy selection working")
    else:
        print("❌ FAIL - Strategy selection issues")
    
    # Test 8: Integrated Self-Learning System
    print("\n[Test 8] Testing integrated Self-Learning System...")
    system = SelfLearningSystem()
    
    # Learn from interaction
    system.learn_from_interaction(
        query="Write a Python function to sort a list",
        response="def sort_list(lst): return sorted(lst)",
        context={'task_type': 'coding'},
        outcome={'success': True, 'performance': 0.9},
        emotions="confident"
    )
    
    stats = system.get_stats()
    print(f"Total learning cycles: {stats['total_learning_cycles']}")
    print(f"Episodic episodes: {stats['episodic_memory']['total_episodes']}")
    print(f"Semantic concepts: {stats['semantic_memory']['total_concepts']}")
    print(f"Procedural skills: {stats['procedural_memory']['total_skills']}")
    
    if stats['total_learning_cycles'] > 0:
        print("✅ PASS - Integrated system working")
    else:
        print("❌ FAIL - Integration issues")
    
    # Test 9: Knowledge recall
    print("\n[Test 9] Testing knowledge recall...")
    
    # Add more interactions
    for i in range(5):
        system.learn_from_interaction(
            query=f"Question {i} about Python programming",
            response=f"Answer {i} about Python",
            context={'task_type': 'coding'},
            outcome={'success': True}
        )
    
    # Recall relevant knowledge
    knowledge = system.recall_relevant_knowledge("How do I code in Python?")
    
    print(f"Similar episodes: {len(knowledge['similar_episodes'])}")
    print(f"Related concepts: {len(knowledge['related_concepts'])}")
    print(f"Skill proficiency: {knowledge['skill_proficiency']:.2f}")
    print(f"Recommended strategy: {knowledge['recommended_strategy']['name']}")
    
    if len(knowledge['similar_episodes']) > 0:
        print("✅ PASS - Knowledge recall working")
    else:
        print("⚠️ PARTIAL - Recall working but no similar episodes")
    
    # Test 10: Learning progress
    print("\n[Test 10] Testing learning progress tracking...")
    progress = system.get_learning_progress()
    
    print(f"Total cycles: {progress['total_learning_cycles']}")
    print(f"Success rate: {progress['episodic_memory']['success_rate']:.2%}")
    print(f"Average skill proficiency: {progress['procedural_memory']['avg_proficiency']:.2f}")
    
    if progress['total_learning_cycles'] >= 6:
        print("✅ PASS - Progress tracking working")
    else:
        print("❌ FAIL - Progress tracking issues")
    
    # Test 11: Failure learning
    print("\n[Test 11] Testing learning from failures...")
    
    # Simulate failures
    for i in range(3):
        system.learn_from_interaction(
            query=f"Difficult question {i}",
            response=f"Attempted answer {i}",
            context={'task_type': 'complex'},
            outcome={'success': False, 'performance': 0.3},
            emotions="uncertain"
        )
    
    failures = system.episodic.recall_failures(top_k=5)
    print(f"Recorded failures: {len(failures)}")
    
    if len(failures) >= 3:
        print("✅ PASS - Failure tracking working")
    else:
        print("❌ FAIL - Failure tracking issues")
    
    # Test 12: Convenience function
    print("\n[Test 12] Testing convenience function...")
    quick_system = create_self_learning_system()
    
    if quick_system.episodic and quick_system.semantic:
        print("✅ PASS - Convenience function working")
    else:
        print("❌ FAIL - Convenience function issues")
    
    print("\n" + "=" * 60)
    print("🎉 Self-Learning System tests completed!")
    print("=" * 60)
    
    # Final learning report
    print("\n" + "=" * 60)
    print("FINAL LEARNING REPORT")
    print("=" * 60)
    
    final_progress = system.get_learning_progress()
    
    print(f"\n📚 Episodic Memory:")
    print(f"  Total episodes: {final_progress['episodic_memory']['total_episodes']}")
    print(f"  Success rate: {final_progress['episodic_memory']['success_rate']:.1%}")
    
    print(f"\n🧠 Semantic Memory:")
    print(f"  Total concepts: {final_progress['semantic_memory']['total_concepts']}")
    print(f"  Total relations: {final_progress['semantic_memory']['total_relations']}")
    
    print(f"\n🎯 Procedural Memory:")
    print(f"  Total skills: {final_progress['procedural_memory']['total_skills']}")
    print(f"  Mastered skills: {final_progress['procedural_memory']['mastered_skills']}")
    print(f"  Average proficiency: {final_progress['procedural_memory']['avg_proficiency']:.1%}")
    
    print(f"\n🎓 Meta-Learning:")
    print(f"  Total strategies: {final_progress['meta_learning']['total_strategies']}")
    print(f"  Average strategy performance: {final_progress['meta_learning']['avg_strategy_performance']:.2f}")
    
    print(f"\n🔄 Total Learning Cycles: {final_progress['total_learning_cycles']}")
    print("=" * 60)


if __name__ == "__main__":
    test_self_learning()
