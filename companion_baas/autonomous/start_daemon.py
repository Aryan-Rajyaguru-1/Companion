#!/usr/bin/env python3
"""
Start Autonomous Brain Daemon
==============================

Entry point for daemon service
"""

import sys
import os

# Add project to path
project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_dir)

from companion_baas.core.brain import CompanionBrain
from companion_baas.autonomous.autonomous_daemon import AutonomousDaemon, is_daemon_running
from companion_baas.autonomous.config import get_autonomous_config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Start daemon"""
    logger.info("🚀 Starting Autonomous Brain Daemon...")
    
    # Check if already running
    if is_daemon_running():
        logger.error("❌ Daemon already running! Check autonomous_daemon.pid")
        sys.exit(1)
    
    # Create brain with AGI and autonomy enabled
    logger.info("🧠 Initializing Companion Brain...")
    brain = CompanionBrain(
        app_type="autonomous",
        enable_agi=True,
        enable_autonomy=True,
        enable_caching=True,
        enable_search=True,
        enable_learning=True
    )
    
    logger.info("✅ Brain initialized")
    
    # Get config
    config = get_autonomous_config()
    
    # Create and start daemon
    daemon = AutonomousDaemon(brain, config)
    
    logger.info("🤖 Starting autonomous daemon...")
    daemon.start()


if __name__ == '__main__':
    main()
