"""
Companion BaaS SDK - Now with AGI Capabilities!
================================================

ONE LINE TO AGI:
    from companion_baas import Brain
    brain = Brain()  # Full AGI ready!

Traditional API:
    from companion_baas.sdk import BrainClient
    client = BrainClient()
"""

from .client import BrainClient, quick_chat, quick_search, Brain

__all__ = ['BrainClient', 'Brain', 'quick_chat', 'quick_search']
