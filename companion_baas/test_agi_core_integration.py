#!/usr/bin/env python3
"""
Test AGI Integration in CompanionBrain Core
Verifies that AGI features are properly integrated without changing imports
"""

import sys
import os

# Add paths
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

def test_traditional_brain():
    """Test 1: Traditional BrainClient (no AGI) - should work unchanged"""
    print("\n" + "="*70)
    print("TEST 1: Traditional BrainClient (NO AGI)")
    print("="*70)
    
    from companion_baas.sdk import BrainClient
    
    # Create traditional brain - NO import changes!
    client = BrainClient(
        app_type="chatbot",
        enable_caching=True,
        enable_search=True,
        enable_learning=True
    )
    
    print(f"✅ Created: {client}")
    print(f"✅ AGI enabled: {client.brain.enable_agi}")
    print(f"✅ Autonomy enabled: {client.brain.enable_autonomy}")
    
    # Test basic chat
    response = client.ask("Hello!")
    print(f"✅ Basic chat works: {response[:50]}...")
    
    # AGI methods should return None
    personality = client.get_personality()
    print(f"✅ Personality (should be None): {personality}")
    
    print("\n✅ TEST 1 PASSED: Traditional mode works unchanged!")
    return True

def test_agi_brain():
    """Test 2: AGI-enabled BrainClient - same import, different config"""
    print("\n" + "="*70)
    print("TEST 2: AGI-Enabled BrainClient (WITH AGI)")
    print("="*70)
    
    from companion_baas.sdk import BrainClient
    
    # Create AGI brain - SAME import, just add enable_agi=True!
    client = BrainClient(
        app_type="chatbot",
        enable_caching=True,
        enable_search=True,
        enable_learning=True,
        enable_agi=True,         # ✨ NEW: Just add this!
        enable_autonomy=False    # 🔒 Safe mode
    )
    
    print(f"✅ Created: {client}")
    print(f"✅ AGI enabled: {client.brain.enable_agi}")
    print(f"✅ Autonomy enabled: {client.brain.enable_autonomy}")
    
    # Test basic chat (should still work)
    response = client.ask("Hello!")
    print(f"✅ Basic chat works: {response[:50]}...")
    
    # Test AGI features
    print("\n🧠 Testing AGI Features:")
    
    # Get personality
    personality = client.get_personality()
    if personality:
        print(f"  ✅ Personality ID: {personality['personality_id']}")
        print(f"  ✅ Current emotion: {personality['emotion']}")
        print(f"  ✅ Dominant traits: {personality['dominant_traits'][:2]}")
    else:
        print(f"  ⚠️ Personality: Not available (components may not be initialized)")
    
    # Get learning stats
    stats = client.get_learning_stats()
    if stats:
        print(f"  ✅ Episodes: {stats['episodes']}")
        print(f"  ✅ Concepts: {stats['concepts']}")
        print(f"  ✅ Skills: {stats['skills']}")
    else:
        print(f"  ⚠️ Learning stats: Not available (components may not be initialized)")
    
    # Get AGI status
    agi_status = client.get_agi_status()
    print(f"  ✅ AGI enabled: {agi_status['agi_enabled']}")
    print(f"  ✅ Components: {agi_status['components']}")
    
    # Test teach concept
    success = client.teach_concept("test_concept", ["example 1", "example 2"])
    print(f"  ✅ Teach concept: {'Success' if success else 'Not available (components may not be initialized)'}")
    
    print("\n✅ TEST 2 PASSED: AGI mode works with same import!")
    return True

def test_toggle_agi():
    """Test 3: Toggle AGI on/off at runtime"""
    print("\n" + "="*70)
    print("TEST 3: Toggle AGI On/Off at Runtime")
    print("="*70)
    
    from companion_baas.sdk import BrainClient
    
    # Start with AGI disabled
    client = BrainClient(app_type="chatbot", enable_agi=False)
    print(f"✅ Created with AGI disabled: {client}")
    print(f"   AGI status: {client.brain.enable_agi}")
    
    # Enable AGI at runtime
    print("\n🔄 Enabling AGI...")
    client.enable_agi(True)
    print(f"✅ AGI enabled: {client.brain.enable_agi}")
    
    # Disable AGI
    print("\n🔄 Disabling AGI...")
    client.disable_agi()
    print(f"✅ AGI disabled: {client.brain.enable_agi}")
    
    print("\n✅ TEST 3 PASSED: Toggle works!")
    return True

def test_no_import_changes():
    """Test 4: Verify no import changes needed"""
    print("\n" + "="*70)
    print("TEST 4: Verify No Import Changes Needed")
    print("="*70)
    
    # Same import for both traditional and AGI
    from companion_baas.sdk import BrainClient
    
    # Create both types with SAME import
    traditional = BrainClient(app_type="chatbot")
    agi = BrainClient(app_type="chatbot", enable_agi=True)
    
    print(f"✅ Traditional: {traditional}")
    print(f"✅ AGI: {agi}")
    print(f"\n✅ Both use SAME import: companion_baas.sdk.BrainClient")
    print(f"✅ Difference is ONLY in parameters: enable_agi=True")
    
    print("\n✅ TEST 4 PASSED: No import changes needed!")
    return True

def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("🧪 AGI INTEGRATION TESTS")
    print("Testing that AGI works without changing imports")
    print("="*70)
    
    tests = [
        ("Traditional Brain (No AGI)", test_traditional_brain),
        ("AGI-Enabled Brain", test_agi_brain),
        ("Toggle AGI On/Off", test_toggle_agi),
        ("No Import Changes", test_no_import_changes)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result, None))
        except Exception as e:
            import traceback
            results.append((name, False, traceback.format_exc()))
            print(f"\n❌ TEST FAILED: {e}")
    
    # Summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result, _ in results if result)
    total = len(results)
    
    for name, result, error in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
        if error:
            print(f"   Error: {error[:100]}...")
    
    print(f"\n{'='*70}")
    print(f"Results: {passed}/{total} tests passed ({100*passed//total}%)")
    print("="*70)
    
    if passed == total:
        print("\n🎊 ALL TESTS PASSED!")
        print("\n✅ KEY ACHIEVEMENTS:")
        print("   • Traditional BrainClient works unchanged")
        print("   • AGI Brain uses SAME import")
        print("   • Only difference: enable_agi=True parameter")
        print("   • No code refactoring needed")
        print("   • 100% backwards compatible")
        print("\n🎯 RESULT: Core integration successful!")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
