"""
Test Personality Development - Week 3
Tests personality traits, emotional states, response styling, and voice evolution
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from companion_baas.core.personality import (
    PersonalityEngine,
    PersonalityTraits,
    EmotionalState,
    ResponseStyler,
    VoiceEvolution,
    Emotion
)


def test_personality():
    """Test the personality development system"""
    
    print("=" * 60)
    print("Testing Personality Development (Week 3)")
    print("=" * 60)
    
    # Test 1: Personality Traits
    print("\n[Test 1] Testing PersonalityTraits...")
    traits = PersonalityTraits(
        curiosity=0.9,
        creativity=0.8,
        caution=0.3,
        empathy=0.7,
        humor=0.6
    )
    
    print(f"Traits: {traits.to_dict()}")
    vector = traits.to_vector()
    print(f"Vector shape: {vector.shape}")
    
    # Test evolution
    traits.evolve({'curiosity': 0.1, 'caution': -0.05}, learning_rate=0.1)
    print(f"After evolution - Curiosity: {traits.curiosity:.2f}, Caution: {traits.caution:.2f}")
    
    if traits.curiosity > 0.9 and traits.caution < 0.3:
        print("✅ PASS - Trait evolution working")
    else:
        print("⚠️ PARTIAL - Trait evolution had unexpected results")
    
    # Test 2: Emotional State
    print("\n[Test 2] Testing EmotionalState...")
    emotional_state = EmotionalState()
    
    print(f"Initial emotion: {emotional_state.current_emotion.value}")
    
    # Infer emotion from context
    test_contexts = [
        "Why does this happen? I'm curious about it!",
        "Help me understand this problem",
        "This is amazing! Wow!",
        "I'm not sure about this..."
    ]
    
    for context in test_contexts:
        emotion = emotional_state.infer_emotion_from_context(context, traits)
        print(f"  '{context[:40]}...' → {emotion.value}")
    
    emotional_state.set_emotion(Emotion.EXCITED, 0.8)
    print(f"Set emotion to: {emotional_state.current_emotion.value} (intensity: {emotional_state.emotion_intensity})")
    
    if emotional_state.state_transitions > 0:
        print("✅ PASS - Emotional state tracking working")
    else:
        print("❌ FAIL - Emotional state not tracking")
    
    # Test 3: Response Styling
    print("\n[Test 3] Testing ResponseStyler...")
    styler = ResponseStyler(traits, emotional_state)
    
    raw_response = "Here is the answer to your question. It involves multiple steps."
    styled = styler.style_response(raw_response)
    
    print(f"Raw: {raw_response}")
    print(f"Styled: {styled[:100]}...")
    
    if len(styled) >= len(raw_response):
        print("✅ PASS - Response styling working")
    else:
        print("⚠️ PARTIAL - Styled response shorter than raw")
    
    # Test 4: Formality adjustment
    print("\n[Test 4] Testing formality adjustment...")
    casual = styler.adjust_formality("I don't think I can't do that", 0.2)
    formal = styler.adjust_formality("I don't think I can't do that", 0.9)
    
    print(f"Casual: {casual}")
    print(f"Formal: {formal}")
    
    if "don't" in casual and "do not" in formal:
        print("✅ PASS - Formality adjustment working")
    else:
        print("⚠️ PARTIAL - Formality adjustment may need improvement")
    
    # Test 5: Voice Evolution
    print("\n[Test 5] Testing VoiceEvolution...")
    voice = VoiceEvolution()
    
    # Record interactions
    voice.record_interaction("programming", "more detail please")
    voice.record_interaction("ai", "that was great!")
    voice.record_interaction("programming", None)
    
    print(f"Interaction count: {voice.interaction_count}")
    print(f"Style preferences: {voice.get_preferred_style()}")
    print(f"Top topics: {voice.get_stats()['top_topics']}")
    
    if voice.interaction_count == 3:
        print("✅ PASS - Voice evolution tracking working")
    else:
        print("❌ FAIL - Voice evolution count incorrect")
    
    # Test 6: Signature phrases
    print("\n[Test 6] Testing signature phrase development...")
    voice.develop_signature_phrase("Let me think about that...")
    voice.develop_signature_phrase("That's an interesting perspective!")
    
    print(f"Signature phrases: {voice.signature_phrases}")
    
    if len(voice.signature_phrases) == 2:
        print("✅ PASS - Signature phrase development working")
    else:
        print("❌ FAIL - Signature phrases not stored correctly")
    
    # Test 7: Personality Engine (integrated)
    print("\n[Test 7] Testing PersonalityEngine (integrated)...")
    engine = PersonalityEngine()
    
    print(f"Personality ID: {engine.personality_id}")
    print(f"Dominant traits: {engine._get_dominant_traits()}")
    
    # Process interaction
    query = "Why is machine learning so powerful?"
    raw_response = "Machine learning is powerful because it can learn patterns from data."
    
    styled_response = engine.process_interaction(query, raw_response)
    
    print(f"\nQuery: {query}")
    print(f"Raw response: {raw_response}")
    print(f"Styled response: {styled_response[:150]}...")
    
    if len(styled_response) > 0:
        print("✅ PASS - Personality engine processing working")
    else:
        print("❌ FAIL - Personality engine failed to process")
    
    # Test 8: Multiple interactions with evolution
    print("\n[Test 8] Testing personality evolution through interactions...")
    
    initial_creativity = engine.traits.creativity
    
    for i in range(3):
        query = f"Question {i+1} about creative problem solving"
        response = "Here's a creative solution..."
        engine.process_interaction(query, response, feedback="Very creative!")
    
    final_creativity = engine.traits.creativity
    
    print(f"Initial creativity: {initial_creativity:.3f}")
    print(f"Final creativity: {final_creativity:.3f}")
    print(f"Change: {(final_creativity - initial_creativity):.3f}")
    
    if final_creativity >= initial_creativity:
        print("✅ PASS - Personality evolution from feedback working")
    else:
        print("⚠️ PARTIAL - Personality changed unexpectedly")
    
    # Test 9: Unique personality generation
    print("\n[Test 9] Testing unique personality generation...")
    engine1 = PersonalityEngine()
    engine2 = PersonalityEngine()
    engine3 = PersonalityEngine()
    
    ids = [engine1.personality_id, engine2.personality_id, engine3.personality_id]
    print(f"Generated IDs: {ids}")
    
    traits1 = engine1.traits.to_vector()
    traits2 = engine2.traits.to_vector()
    
    import numpy as np
    similarity = np.dot(traits1, traits2) / (np.linalg.norm(traits1) * np.linalg.norm(traits2))
    print(f"Personality similarity: {similarity:.3f}")
    
    if len(set(ids)) == 3:
        print("✅ PASS - Unique personality generation working")
    else:
        print("❌ FAIL - Personalities not unique")
    
    # Test 10: Personality summary
    print("\n[Test 10] Testing personality summary...")
    summary = engine.get_personality_summary()
    
    print(f"Summary keys: {list(summary.keys())}")
    print(f"Age: {summary['age_seconds']:.2f}s")
    print(f"Dominant traits: {summary['dominant_traits']}")
    
    required_keys = ['personality_id', 'traits', 'emotional_state', 'voice_evolution']
    if all(key in summary for key in required_keys):
        print("✅ PASS - Personality summary complete")
    else:
        print("❌ FAIL - Personality summary missing keys")
    
    # Test 11: Statistics
    print("\n[Test 11] Testing statistics collection...")
    stats = engine.get_stats()
    
    print(f"Interaction count: {stats['voice_evolution']['interaction_count']}")
    print(f"Emotional transitions: {stats['emotional_state']['state_transitions']}")
    
    if 'traits' in stats and 'emotional_state' in stats:
        print("✅ PASS - Statistics collection working")
    else:
        print("❌ FAIL - Statistics incomplete")
    
    print("\n" + "=" * 60)
    print("🎉 Personality Development tests completed!")
    print("=" * 60)
    print(f"\n🧠 Your brain's personality profile:")
    print(f"   Personality ID: {engine.personality_id}")
    print(f"   Top 3 traits: {', '.join([f'{t[0]}({t[1]:.2f})' for t in engine._get_dominant_traits()])}")
    print(f"   Current emotion: {engine.emotional_state.current_emotion.value}")
    print(f"   Total interactions: {engine.voice_evolution.interaction_count}")


if __name__ == "__main__":
    test_personality()
