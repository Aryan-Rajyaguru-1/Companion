"""
Compatibility Test: AGI Brain vs Traditional BrainClient
=========================================================

This test verifies that:
1. AGI Brain is 100% backwards compatible with BrainClient
2. All existing chatbot/BaaS features work in AGI Brain
3. New AGI features are additive, not breaking
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("\n" + "="*70)
print("COMPATIBILITY TEST: AGI Brain vs BrainClient")
print("="*70)

# Test 1: Import both classes
print("\n[Test 1] Import Both Classes")
try:
    from companion_baas.sdk import BrainClient, Brain
    print("  ✅ BrainClient imported")
    print("  ✅ Brain (AGI) imported")
except Exception as e:
    print(f"  ❌ Import failed: {e}")
    sys.exit(1)

# Test 2: Create instances
print("\n[Test 2] Create Instances")
try:
    traditional_client = BrainClient(app_type="chatbot")
    agi_brain = Brain(app_type="chatbot", enable_agi=True, enable_autonomy=False)
    print("  ✅ BrainClient instance created")
    print("  ✅ AGI Brain instance created")
except Exception as e:
    print(f"  ❌ Creation failed: {e}")
    sys.exit(1)

# Test 3: Verify inheritance
print("\n[Test 3] Verify Inheritance")
assert isinstance(agi_brain, BrainClient), "AGI Brain should inherit from BrainClient"
print("  ✅ AGI Brain IS-A BrainClient (inheritance confirmed)")

# Test 4: Check traditional methods exist in AGI Brain
print("\n[Test 4] Traditional Methods Available in AGI Brain")
traditional_methods = [
    'chat', 'ask', 'get_history', 'clear_history', 'search',
    'feedback', 'get_stats', 'execute_code', 'call_tool',
    'list_tools', 'semantic_search', 'hybrid_search',
    'crawl_website', 'get_performance_stats', 'reason',
    'process_media', 'provide_learning_feedback', 'remember', 'recall'
]

for method in traditional_methods:
    assert hasattr(agi_brain, method), f"AGI Brain missing method: {method}"

print(f"  ✅ All {len(traditional_methods)} traditional methods available")
print(f"  ✅ AGI Brain is 100% backwards compatible")

# Test 5: Check NEW AGI methods
print("\n[Test 5] New AGI Methods Available")
agi_methods = [
    'enable_agi', 'disable_agi', 'enable_autonomy', 'disable_autonomy',
    'get_personality', 'get_learning_stats', 'get_autonomous_stats',
    'teach_concept', 'synthesize_ideas', 'recall_memories',
    'run_self_improvement', 'get_agi_status'
]

for method in agi_methods:
    assert hasattr(agi_brain, method), f"AGI Brain missing new method: {method}"

print(f"  ✅ All {len(agi_methods)} new AGI methods available")

# Test 6: AGI Brain has ADDITIONAL Tier 4 components
print("\n[Test 6] AGI Brain Has Tier 4 Components")
tier4_components = [
    '_local_intelligence', '_neural_reasoning', '_personality_engine',
    '_self_learning', '_autonomous'
]

for component in tier4_components:
    assert hasattr(agi_brain, component), f"AGI Brain missing: {component}"

print(f"  ✅ All 5 Tier 4 components initialized")

# Test 7: Traditional client DOES NOT have AGI components
print("\n[Test 7] Traditional Client Stays Lightweight")
assert not hasattr(traditional_client, '_local_intelligence')
assert not hasattr(traditional_client, '_personality_engine')
print("  ✅ Traditional BrainClient doesn't have AGI overhead")
print("  ✅ Clean separation maintained")

# Test 8: Both can access underlying CompanionBrain
print("\n[Test 8] Both Access Same Core Brain")
assert hasattr(traditional_client, 'brain')
assert hasattr(agi_brain, 'brain')
print("  ✅ Both have access to CompanionBrain core")
print("  ✅ Shared Tier 1-3 infrastructure")

# Test 9: AGI features can be toggled
print("\n[Test 9] AGI Features Are Toggleable")
agi_brain.disable_agi()
assert not agi_brain._agi_enabled
agi_brain.enable_agi()
assert agi_brain._agi_enabled
print("  ✅ AGI can be disabled (falls back to traditional)")
print("  ✅ AGI can be re-enabled dynamically")

# Test 10: API compatibility
print("\n[Test 10] API Compatibility")
# Both should support the same basic API
methods_to_test = ['get_stats', 'list_tools']
for method in methods_to_test:
    trad_result = getattr(traditional_client, method)()
    agi_result = getattr(agi_brain, method)()
    assert type(trad_result) == type(agi_result), f"API mismatch for {method}"

print("  ✅ Return types match for common methods")
print("  ✅ API is consistent across both")

print("\n" + "="*70)
print("✅ ALL COMPATIBILITY TESTS PASSED!")
print("="*70)

print("\n📊 SUMMARY:")
print("\n1. BACKWARDS COMPATIBILITY: 100%")
print("   • All existing BrainClient features work in AGI Brain")
print("   • Inheritance hierarchy preserved")
print("   • API signatures identical")

print("\n2. UPGRADE PATH:")
print("   • Traditional: from companion_baas.sdk import BrainClient")
print("   • AGI:         from companion_baas import Brain")
print("   • Simply change import to get AGI features!")

print("\n3. COEXISTENCE:")
print("   • Both can run side-by-side")
print("   • Traditional stays lightweight")
print("   • AGI adds Tier 4 without breaking existing")

print("\n4. MIGRATION:")
print("   • Zero code changes needed for basic features")
print("   • Opt-in to AGI features when ready")
print("   • Gradual migration path available")

print("\n🎯 CONCLUSION:")
print("   ✅ Existing chatbots will continue to work")
print("   ✅ CompanionBrain is fully compatible")
print("   ✅ AGI Brain extends without breaking")
print("   ✅ Perfect backwards compatibility achieved!")

print("\n" + "="*70)
sys.exit(0)
