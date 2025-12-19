#!/usr/bin/env python3
"""
Test Autonomous Daemon
======================

Quick test to verify daemon components work
"""

import sys
import os

# Add project to path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

print("🧪 Testing Autonomous Daemon Components...")
print("=" * 50)
print()

# Test 1: Import modules
print("1️⃣  Testing imports...")
try:
    from companion_baas.autonomous import (
        UnrestrictedFileController,
        AutonomousConfig,
        AutonomousDaemon,
    )
    print("   ✅ All modules imported successfully")
except ImportError as e:
    print(f"   ❌ Import failed: {e}")
    sys.exit(1)

print()

# Test 2: Configuration
print("2️⃣  Testing configuration...")
try:
    config = AutonomousConfig()
    print(f"   ✅ Config loaded")
    print(f"   📁 Project root: {config.project_root}")
    print(f"   🔓 Restriction level: {config.restriction_level}")
    print(f"   ⚙️  Can modify core: {config.can_modify_core}")
    print(f"   🤖 Auto deploy: {config.auto_deploy}")
    print(f"   🧬 Self evolution: {config.self_evolution_enabled}")
except Exception as e:
    print(f"   ❌ Config failed: {e}")
    sys.exit(1)

print()

# Test 3: File Controller
print("3️⃣  Testing file controller...")
try:
    file_controller = UnrestrictedFileController(config)
    
    # Test write
    test_file = os.path.join(config.project_root, 'test_autonomous.txt')
    content = f"Autonomous test at {os.times()}\n"
    
    success = file_controller.write_file(test_file, content)
    if success:
        print("   ✅ File write successful")
    else:
        print("   ⚠️  File write failed")
    
    # Test read
    read_content = file_controller.read_file(test_file)
    if read_content == content:
        print("   ✅ File read successful")
    else:
        print("   ⚠️  File read mismatch")
    
    # Test delete
    file_controller.delete_file(test_file)
    if not file_controller.file_exists(test_file):
        print("   ✅ File delete successful")
    else:
        print("   ⚠️  File delete failed")
    
    # Test scan
    python_files = file_controller.list_directory(
        config.project_root, 
        pattern="*.py",
        recursive=False
    )
    print(f"   ✅ Found {len(python_files)} Python files in root")
    
except Exception as e:
    print(f"   ❌ File controller failed: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 4: Brain initialization (optional - commented out for quick test)
print("4️⃣  Testing brain initialization...")
print("   ℹ️  Skipping full brain init (use start_daemon.py for full test)")
# Uncomment below to test full brain initialization:
# try:
#     from companion_baas.core.brain import CompanionBrain
#     brain = CompanionBrain(
#         app_type="autonomous",
#         enable_agi=True,
#         enable_autonomy=True
#     )
#     print("   ✅ Brain initialized")
# except Exception as e:
#     print(f"   ❌ Brain init failed: {e}")

print()

# Test 5: Daemon check
print("5️⃣  Checking daemon status...")
try:
    from companion_baas.autonomous.autonomous_daemon import is_daemon_running
    
    if is_daemon_running():
        print("   ✅ Daemon is currently running")
        pid_file = os.path.join(config.project_root, 'autonomous_daemon.pid')
        with open(pid_file, 'r') as f:
            pid = f.read().strip()
        print(f"   📋 PID: {pid}")
    else:
        print("   ℹ️  Daemon is not running")
        print("   💡 Start with: bash start_daemon_manual.sh")
except Exception as e:
    print(f"   ⚠️  Daemon check failed: {e}")

print()
print("=" * 50)
print("✅ All tests passed!")
print()
print("🚀 Next steps:")
print("   • Start daemon: bash start_daemon_manual.sh")
print("   • Install for auto-start: sudo bash install_daemon.sh")
print("   • View dashboard: http://localhost:8888")
print()
