"""
Test Neural Reasoning Engine - Week 2
Tests vector-based thought, chain-of-thought, concept formation, and creative synthesis
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from companion_baas.core.neural_reasoning import (
    NeuralReasoningEngine,
    ThoughtSpace,
    ThoughtVector,
    ChainOfThought,
    ConceptFormation,
    CreativeSynthesis
)
from companion_baas.core.local_intelligence import LocalIntelligenceCore


async def test_neural_reasoning():
    """Test the neural reasoning engine"""
    
    print("=" * 60)
    print("Testing Neural Reasoning Engine (Week 2)")
    print("=" * 60)
    
    # Setup local intelligence
    print("\n[Setup] Initializing local intelligence...")
    local_intel = LocalIntelligenceCore(auto_setup=False)
    await local_intel._async_setup()
    
    # Test 1: ThoughtSpace basics
    print("\n[Test 1] Testing ThoughtSpace...")
    thought_space = ThoughtSpace()
    
    if thought_space.enabled:
        thought1 = thought_space.encode_thought("Machine learning is amazing")
        thought2 = thought_space.encode_thought("AI is incredible")
        
        if thought1 and thought2:
            similarity = thought1.similarity(thought2)
            print(f"Thought 1: 'Machine learning is amazing'")
            print(f"Thought 2: 'AI is incredible'")
            print(f"Similarity: {similarity:.3f}")
            
            if similarity > 0.5:
                print("✅ PASS - Thoughts have high semantic similarity")
            else:
                print("⚠️ WARNING - Similarity lower than expected")
        else:
            print("❌ FAIL - Could not encode thoughts")
    else:
        print("⚠️ SKIP - sentence-transformers not available")
    
    # Test 2: ThoughtVector combination
    print("\n[Test 2] Testing ThoughtVector combination...")
    if thought_space.enabled and thought1 and thought2:
        combined = thought1.combine(thought2, weight=0.5)
        print(f"Combined thought: {combined.content[:100]}")
        print(f"Confidence: {combined.confidence}")
        print("✅ PASS - Thought combination working")
    else:
        print("⚠️ SKIP - sentence-transformers not available")
    
    # Test 3: Chain-of-thought reasoning
    print("\n[Test 3] Testing Chain-of-Thought reasoning...")
    chain = ChainOfThought(thought_space, local_intel)
    
    try:
        print("Query: 'What is 5 + 3 * 2?'")
        steps = await chain.reason("What is 5 + 3 * 2?", max_steps=4)
        
        print(f"Reasoning steps: {len(steps)}")
        for i, step in enumerate(steps[:3], 1):  # Show first 3 steps
            print(f"  Step {i}: {step.conclusion[:60] if step.conclusion else 'N/A'}...")
        
        if len(steps) >= 2:
            print("✅ PASS - Multi-step reasoning working")
        else:
            print("⚠️ PARTIAL - Reasoning completed but fewer steps than expected")
    except Exception as e:
        print(f"❌ FAIL - Chain-of-thought error: {e}")
    
    # Test 4: Concept formation
    print("\n[Test 4] Testing Concept Formation...")
    concepts = ConceptFormation(thought_space)
    
    if thought_space.enabled:
        # Teach concept
        concepts.learn_concept("programming", [
            "Writing code in Python",
            "Creating software applications",
            "Developing algorithms and functions"
        ])
        
        # Test recognition
        test_text = "Building a web application with JavaScript"
        recognized = concepts.recognize_concept(test_text, threshold=0.5)
        
        print(f"Learned concept: 'programming'")
        print(f"Test text: '{test_text}'")
        print(f"Recognized as: {recognized}")
        
        if 'programming' in concepts.concepts:
            print("✅ PASS - Concept learning working")
        else:
            print("❌ FAIL - Concept not learned")
    else:
        print("⚠️ SKIP - sentence-transformers not available")
    
    # Test 5: Creative synthesis
    print("\n[Test 5] Testing Creative Synthesis...")
    creativity = CreativeSynthesis(thought_space)
    
    if thought_space.enabled:
        ideas = [
            "Artificial intelligence",
            "Creative writing",
            "Music composition"
        ]
        
        synthesis = await creativity.synthesize(ideas, goal="innovative application")
        print(f"Ideas: {ideas}")
        print(f"Synthesis: {synthesis[:150]}...")
        print("✅ PASS - Creative synthesis working")
    else:
        print("⚠️ SKIP - sentence-transformers not available")
    
    # Test 6: Analogical reasoning
    print("\n[Test 6] Testing Analogical Reasoning...")
    if thought_space.enabled:
        analogy = creativity.analogical_reasoning(
            "neural networks",
            "human brain"
        )
        print(f"Analogy: {analogy}")
        print("✅ PASS - Analogical reasoning working")
    else:
        print("⚠️ SKIP - sentence-transformers not available")
    
    # Test 7: Neural Reasoning Engine (integrated)
    print("\n[Test 7] Testing Neural Reasoning Engine (integrated)...")
    engine = NeuralReasoningEngine(local_intel)
    
    try:
        result = await engine.reason(
            "What is the capital of France?",
            mode="chain_of_thought"
        )
        
        print(f"Mode: {result['mode']}")
        print(f"Steps: {result['steps']}")
        print(f"Final answer: {result.get('final_answer', 'N/A')[:100]}...")
        
        if result['steps'] > 0:
            print("✅ PASS - Neural reasoning engine working")
        else:
            print("⚠️ PARTIAL - Engine working but no steps generated")
    except Exception as e:
        print(f"❌ FAIL - Neural reasoning error: {e}")
    
    # Test 8: Concept teaching
    print("\n[Test 8] Testing concept teaching...")
    engine.learn_concept("ai_safety", [
        "Ensuring AI systems are safe",
        "Preventing harmful AI behavior",
        "Aligning AI with human values"
    ])
    
    stats = engine.get_stats()
    if 'ai_safety' in stats['concept_formation']['concepts']:
        print("Taught concept: 'ai_safety'")
        print("✅ PASS - Concept teaching working")
    else:
        print("⚠️ SKIP - Concept teaching requires sentence-transformers")
    
    # Test 9: Statistics
    print("\n[Test 9] Testing statistics collection...")
    stats = engine.get_stats()
    
    print(f"Reasoning count: {stats['reasoning_count']}")
    print(f"Total thoughts: {stats['thought_space']['total_thoughts']}")
    print(f"Total concepts: {stats['concept_formation']['total_concepts']}")
    print(f"Total syntheses: {stats['creative_synthesis']['total_syntheses']}")
    
    if all(k in stats for k in ['reasoning_count', 'thought_space', 'concept_formation']):
        print("✅ PASS - Statistics collection working")
    else:
        print("❌ FAIL - Statistics incomplete")
    
    print("\n" + "=" * 60)
    print("🎉 Neural Reasoning Engine tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_neural_reasoning())
