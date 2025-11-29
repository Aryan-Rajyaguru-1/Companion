"""
Tier 4 AGI Features - Wrapper Package
======================================

This package provides a clean interface to all Tier 4 AGI components.
It wraps the individual modules from core/ directory for clean imports.

Usage:
    from companion_baas.tier4 import (
        LocalIntelligenceCore,
        NeuralReasoningEngine,
        PersonalityEngine,
        SelfLearningSystem,
        AutonomousSystem
    )
"""

import logging
logger = logging.getLogger(__name__)

# Try to import AGI components from core directory
try:
    from companion_baas.core.local_intelligence import LocalIntelligenceCore
    LOCAL_INTELLIGENCE_AVAILABLE = True
except ImportError as e:
    logger.debug(f"Local Intelligence not available: {e}")
    LOCAL_INTELLIGENCE_AVAILABLE = False
    LocalIntelligenceCore = None

try:
    from companion_baas.core.neural_reasoning import NeuralReasoningEngine
    NEURAL_REASONING_AVAILABLE = True
except ImportError as e:
    logger.debug(f"Neural Reasoning not available: {e}")
    NEURAL_REASONING_AVAILABLE = False
    NeuralReasoningEngine = None

try:
    from companion_baas.core.personality import PersonalityEngine
    PERSONALITY_AVAILABLE = True
except ImportError as e:
    logger.debug(f"Personality Engine not available: {e}")
    PERSONALITY_AVAILABLE = False
    PersonalityEngine = None

try:
    from companion_baas.core.self_learning import SelfLearningSystem
    SELF_LEARNING_AVAILABLE = True
except ImportError as e:
    logger.debug(f"Self-Learning System not available: {e}")
    SELF_LEARNING_AVAILABLE = False
    SelfLearningSystem = None

try:
    from companion_baas.core.autonomous import AutonomousSystem
    AUTONOMOUS_AVAILABLE = True
except ImportError as e:
    logger.debug(f"Autonomous System not available: {e}")
    AUTONOMOUS_AVAILABLE = False
    AutonomousSystem = None

# Check overall availability
AGI_AVAILABLE = any([
    LOCAL_INTELLIGENCE_AVAILABLE,
    NEURAL_REASONING_AVAILABLE,
    PERSONALITY_AVAILABLE,
    SELF_LEARNING_AVAILABLE
])

__all__ = [
    'LocalIntelligenceCore',
    'NeuralReasoningEngine',
    'PersonalityEngine',
    'SelfLearningSystem',
    'AutonomousSystem',
    'AGI_AVAILABLE',
    'LOCAL_INTELLIGENCE_AVAILABLE',
    'NEURAL_REASONING_AVAILABLE',
    'PERSONALITY_AVAILABLE',
    'SELF_LEARNING_AVAILABLE',
    'AUTONOMOUS_AVAILABLE'
]

# Log availability status
if AGI_AVAILABLE:
    available_components = []
    if LOCAL_INTELLIGENCE_AVAILABLE:
        available_components.append("Local Intelligence")
    if NEURAL_REASONING_AVAILABLE:
        available_components.append("Neural Reasoning")
    if PERSONALITY_AVAILABLE:
        available_components.append("Personality")
    if SELF_LEARNING_AVAILABLE:
        available_components.append("Self-Learning")
    if AUTONOMOUS_AVAILABLE:
        available_components.append("Autonomous")
    
    logger.info(f"✅ Tier 4 AGI available: {', '.join(available_components)}")
else:
    logger.warning("⚠️ Tier 4 AGI components not available")
