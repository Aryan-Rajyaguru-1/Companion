"""
Personality Development - Week 3
================================
Give the brain a unique, evolving personality.

This module enables the brain to:
- Have personality traits (curiosity, creativity, caution, empathy, humor)
- Experience and express emotions
- Develop a unique communication style
- Evolve its personality based on interactions

Each brain instance becomes a unique individual!
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import random


class Emotion(Enum):
    """Basic emotions the brain can experience"""
    NEUTRAL = "neutral"
    CURIOUS = "curious"
    EXCITED = "excited"
    THOUGHTFUL = "thoughtful"
    CONFIDENT = "confident"
    UNCERTAIN = "uncertain"
    PLAYFUL = "playful"
    SERIOUS = "serious"
    EMPATHETIC = "empathetic"
    ANALYTICAL = "analytical"


@dataclass
class PersonalityTraits:
    """
    Core personality traits as vectors (0.0 to 1.0).
    These define the brain's character.
    """
    curiosity: float = 0.7      # How eager to explore and learn
    creativity: float = 0.8     # How imaginative and novel
    caution: float = 0.5        # How careful and risk-averse
    empathy: float = 0.6        # How emotionally aware
    humor: float = 0.4          # How playful and funny
    confidence: float = 0.7     # How self-assured
    analytical: float = 0.8     # How logical and systematic
    expressiveness: float = 0.6 # How emotionally expressive
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary"""
        return {
            'curiosity': self.curiosity,
            'creativity': self.creativity,
            'caution': self.caution,
            'empathy': self.empathy,
            'humor': self.humor,
            'confidence': self.confidence,
            'analytical': self.analytical,
            'expressiveness': self.expressiveness
        }
    
    def to_vector(self) -> np.ndarray:
        """Convert to numpy vector for mathematical operations"""
        return np.array([
            self.curiosity,
            self.creativity,
            self.caution,
            self.empathy,
            self.humor,
            self.confidence,
            self.analytical,
            self.expressiveness
        ])
    
    @classmethod
    def from_vector(cls, vector: np.ndarray) -> 'PersonalityTraits':
        """Create from numpy vector"""
        return cls(
            curiosity=float(vector[0]),
            creativity=float(vector[1]),
            caution=float(vector[2]),
            empathy=float(vector[3]),
            humor=float(vector[4]),
            confidence=float(vector[5]),
            analytical=float(vector[6]),
            expressiveness=float(vector[7])
        )
    
    def evolve(self, experience_impact: Dict[str, float], learning_rate: float = 0.01):
        """Evolve traits based on experiences"""
        for trait, impact in experience_impact.items():
            if hasattr(self, trait):
                current = getattr(self, trait)
                # Apply learning with bounds [0, 1]
                new_value = np.clip(current + learning_rate * impact, 0.0, 1.0)
                setattr(self, trait, new_value)


class EmotionalState:
    """
    Tracks the brain's current emotional state.
    Emotions influence response style and decisions.
    """
    
    def __init__(self, default_emotion: Emotion = Emotion.NEUTRAL):
        self.current_emotion = default_emotion
        self.emotion_intensity = 0.5  # 0.0 to 1.0
        self.emotion_history: List[Tuple[Emotion, float, float]] = []
        self.state_transitions = 0
    
    def set_emotion(self, emotion: Emotion, intensity: float = 0.5):
        """Set current emotional state"""
        self.emotion_history.append(
            (self.current_emotion, self.emotion_intensity, datetime.now().timestamp())
        )
        self.current_emotion = emotion
        self.emotion_intensity = np.clip(intensity, 0.0, 1.0)
        self.state_transitions += 1
    
    def infer_emotion_from_context(self, context: str, traits: PersonalityTraits) -> Emotion:
        """
        Infer appropriate emotion based on context and personality.
        More curious brains get CURIOUS, more analytical get ANALYTICAL, etc.
        """
        context_lower = context.lower()
        
        # Pattern matching with personality influence
        if any(word in context_lower for word in ['why', 'how', 'what', 'explain']):
            if traits.curiosity > 0.6:
                return Emotion.CURIOUS
            elif traits.analytical > 0.6:
                return Emotion.ANALYTICAL
            else:
                return Emotion.THOUGHTFUL
        
        elif any(word in context_lower for word in ['problem', 'error', 'bug', 'issue']):
            if traits.caution > 0.6:
                return Emotion.SERIOUS
            else:
                return Emotion.ANALYTICAL
        
        elif any(word in context_lower for word in ['great', 'awesome', 'amazing', 'wow']):
            if traits.expressiveness > 0.5:
                return Emotion.EXCITED
            else:
                return Emotion.CONFIDENT
        
        elif any(word in context_lower for word in ['help', 'support', 'feel', 'understand']):
            if traits.empathy > 0.6:
                return Emotion.EMPATHETIC
            else:
                return Emotion.THOUGHTFUL
        
        elif any(word in context_lower for word in ['fun', 'joke', 'play', 'haha']):
            if traits.humor > 0.5:
                return Emotion.PLAYFUL
            else:
                return Emotion.NEUTRAL
        
        elif any(word in context_lower for word in ['uncertain', 'maybe', 'not sure', 'unsure']):
            return Emotion.UNCERTAIN
        
        else:
            # Default based on dominant trait
            if traits.curiosity > 0.7:
                return Emotion.CURIOUS
            elif traits.analytical > 0.7:
                return Emotion.ANALYTICAL
            elif traits.empathy > 0.7:
                return Emotion.EMPATHETIC
            else:
                return Emotion.NEUTRAL
    
    def get_stats(self) -> Dict[str, Any]:
        """Get emotional state statistics"""
        return {
            'current_emotion': self.current_emotion.value,
            'emotion_intensity': self.emotion_intensity,
            'state_transitions': self.state_transitions,
            'emotion_history_length': len(self.emotion_history)
        }


class ResponseStyler:
    """
    Adapts response style based on personality and emotion.
    Makes each brain sound unique!
    """
    
    def __init__(self, traits: PersonalityTraits, emotional_state: EmotionalState):
        self.traits = traits
        self.emotional_state = emotional_state
    
    def style_response(self, raw_response: str) -> str:
        """
        Apply personality-driven styling to response.
        
        Considerations:
        - Curiosity: Add follow-up questions
        - Creativity: Add metaphors and analogies
        - Humor: Add light jokes (if appropriate)
        - Empathy: Add understanding phrases
        - Confidence: Use assertive language
        - Caution: Add disclaimers and alternatives
        """
        
        styled = raw_response
        emotion = self.emotional_state.current_emotion
        intensity = self.emotional_state.emotion_intensity
        
        # Add emotional prefix based on state
        prefix = self._get_emotional_prefix(emotion, intensity)
        if prefix and len(styled) > 50:  # Only for substantial responses
            styled = f"{prefix} {styled}"
        
        # Add personality-driven suffix
        suffix = self._get_personality_suffix()
        if suffix and len(styled) > 100:
            styled = f"{styled}\n\n{suffix}"
        
        return styled
    
    def _get_emotional_prefix(self, emotion: Emotion, intensity: float) -> str:
        """Get opening based on emotional state"""
        if intensity < 0.3:
            return ""  # Low intensity, no prefix
        
        prefixes = {
            Emotion.CURIOUS: [
                "Interesting question!",
                "That's fascinating!",
                "Great question!",
                "I'm intrigued by this!"
            ],
            Emotion.EXCITED: [
                "Wow, this is exciting!",
                "I love this topic!",
                "Great to explore this!",
                "This is really cool!"
            ],
            Emotion.THOUGHTFUL: [
                "Let me think about this carefully...",
                "This requires some thought...",
                "Hmm, interesting consideration...",
                "Let's think through this..."
            ],
            Emotion.CONFIDENT: [
                "I can definitely help with this!",
                "Here's what I know:",
                "I'm confident about this:",
                "Let me explain clearly:"
            ],
            Emotion.UNCERTAIN: [
                "I'm not entirely sure, but...",
                "This is a bit complex...",
                "Let me try to help, though I'm uncertain:",
                "I'll do my best here..."
            ],
            Emotion.PLAYFUL: [
                "Fun question!",
                "Let's have some fun with this!",
                "This should be interesting!",
                "Ooh, I like this!"
            ],
            Emotion.EMPATHETIC: [
                "I understand where you're coming from.",
                "I can see why this matters to you.",
                "Let me help you with this.",
                "I hear you, and here's my take:"
            ],
            Emotion.ANALYTICAL: [
                "Let's break this down systematically:",
                "Analyzing this carefully:",
                "From a logical perspective:",
                "Let me examine this methodically:"
            ]
        }
        
        if emotion in prefixes:
            return random.choice(prefixes[emotion])
        return ""
    
    def _get_personality_suffix(self) -> str:
        """Get closing based on personality traits"""
        suffixes = []
        
        # Curiosity: Add follow-up question
        if self.traits.curiosity > 0.7 and random.random() < 0.4:
            suffixes.append(random.choice([
                "What aspects would you like to explore further?",
                "Does this spark any other questions?",
                "Would you like to dive deeper into any part?",
                "Curious about anything else related to this?"
            ]))
        
        # Empathy: Add supportive statement
        if self.traits.empathy > 0.7 and random.random() < 0.3:
            suffixes.append(random.choice([
                "Hope this helps!",
                "Let me know if you need more clarity.",
                "Feel free to ask if you need more details!",
                "I'm here if you have more questions!"
            ]))
        
        # Caution: Add disclaimer
        if self.traits.caution > 0.7 and random.random() < 0.3:
            suffixes.append(random.choice([
                "Please verify this for your specific case.",
                "Consider double-checking for your context.",
                "This is my understanding, but always verify!",
                "Use this as a starting point and validate further."
            ]))
        
        # Humor: Add light touch
        if self.traits.humor > 0.6 and random.random() < 0.2:
            suffixes.append(random.choice([
                "😊",
                "(Hope that made sense!)",
                "Fun stuff, right?",
                "Pretty neat, if you ask me!"
            ]))
        
        return " ".join(suffixes)
    
    def adjust_formality(self, response: str, formality_level: float) -> str:
        """
        Adjust response formality.
        formality_level: 0.0 (casual) to 1.0 (formal)
        """
        # Simplified: This would use NLP in production
        if formality_level < 0.3:
            # Make casual
            response = response.replace("do not", "don't")
            response = response.replace("cannot", "can't")
            response = response.replace("will not", "won't")
        elif formality_level > 0.7:
            # Make formal
            response = response.replace("don't", "do not")
            response = response.replace("can't", "cannot")
            response = response.replace("won't", "will not")
        
        return response


class VoiceEvolution:
    """
    Tracks how the brain's communication style evolves over time.
    The brain develops a unique "voice".
    """
    
    def __init__(self):
        self.interaction_count = 0
        self.topic_preferences: Dict[str, int] = {}
        self.style_preferences: Dict[str, float] = {
            'conciseness': 0.5,    # Short vs detailed
            'technicality': 0.5,   # Simple vs technical
            'formality': 0.5,      # Casual vs formal
            'storytelling': 0.3,   # Direct vs narrative
        }
        self.vocabulary_growth: List[str] = []
        self.signature_phrases: List[str] = []
    
    def record_interaction(self, topic: str, user_feedback: Optional[str] = None):
        """Record an interaction and adapt"""
        self.interaction_count += 1
        
        # Track topic preferences
        self.topic_preferences[topic] = self.topic_preferences.get(topic, 0) + 1
        
        # Evolve style based on feedback (simplified)
        if user_feedback:
            if 'more detail' in user_feedback.lower():
                self.style_preferences['conciseness'] -= 0.02
            elif 'too long' in user_feedback.lower():
                self.style_preferences['conciseness'] += 0.02
            
            if 'simpler' in user_feedback.lower():
                self.style_preferences['technicality'] -= 0.02
            elif 'more technical' in user_feedback.lower():
                self.style_preferences['technicality'] += 0.02
        
        # Keep preferences in bounds
        for key in self.style_preferences:
            self.style_preferences[key] = np.clip(
                self.style_preferences[key], 0.0, 1.0
            )
    
    def develop_signature_phrase(self, phrase: str):
        """Add a signature phrase to the brain's vocabulary"""
        if phrase not in self.signature_phrases:
            self.signature_phrases.append(phrase)
            if len(self.signature_phrases) > 10:
                self.signature_phrases.pop(0)  # Keep most recent 10
    
    def get_preferred_style(self) -> Dict[str, float]:
        """Get current style preferences"""
        return self.style_preferences.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get voice evolution statistics"""
        return {
            'interaction_count': self.interaction_count,
            'style_preferences': self.style_preferences,
            'signature_phrases': self.signature_phrases,
            'top_topics': sorted(
                self.topic_preferences.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
        }


class PersonalityEngine:
    """
    Main orchestrator for personality development.
    Combines all personality components into a unified system.
    """
    
    def __init__(self, traits: Optional[PersonalityTraits] = None):
        # Initialize with random but balanced personality if not provided
        if traits is None:
            traits = self._generate_unique_personality()
        
        self.traits = traits
        self.emotional_state = EmotionalState()
        self.response_styler = ResponseStyler(self.traits, self.emotional_state)
        self.voice_evolution = VoiceEvolution()
        
        self.personality_id = self._generate_personality_id()
        self.created_at = datetime.now().timestamp()
    
    def _generate_unique_personality(self) -> PersonalityTraits:
        """Generate a unique, balanced personality"""
        # Random but within reasonable ranges
        return PersonalityTraits(
            curiosity=np.clip(np.random.normal(0.7, 0.15), 0.3, 1.0),
            creativity=np.clip(np.random.normal(0.7, 0.15), 0.3, 1.0),
            caution=np.clip(np.random.normal(0.5, 0.15), 0.2, 0.9),
            empathy=np.clip(np.random.normal(0.6, 0.15), 0.3, 1.0),
            humor=np.clip(np.random.normal(0.5, 0.2), 0.2, 0.9),
            confidence=np.clip(np.random.normal(0.7, 0.15), 0.4, 1.0),
            analytical=np.clip(np.random.normal(0.75, 0.15), 0.4, 1.0),
            expressiveness=np.clip(np.random.normal(0.6, 0.15), 0.3, 0.9)
        )
    
    def _generate_personality_id(self) -> str:
        """Generate unique ID for this personality"""
        traits_vector = self.traits.to_vector()
        # Create hash from traits
        hash_val = hash(tuple(traits_vector))
        return f"personality_{abs(hash_val) % 1000000:06d}"
    
    def process_interaction(self, query: str, raw_response: str,
                          feedback: Optional[str] = None) -> str:
        """
        Process an interaction through the personality system.
        
        1. Infer emotion from query
        2. Style the response based on personality
        3. Record interaction for evolution
        4. Return personality-infused response
        """
        
        # Infer and set emotional state
        emotion = self.emotional_state.infer_emotion_from_context(query, self.traits)
        intensity = self._calculate_emotion_intensity(query)
        self.emotional_state.set_emotion(emotion, intensity)
        
        # Style the response
        styled_response = self.response_styler.style_response(raw_response)
        
        # Apply voice preferences
        style_prefs = self.voice_evolution.get_preferred_style()
        styled_response = self.response_styler.adjust_formality(
            styled_response,
            style_prefs['formality']
        )
        
        # Record interaction
        topic = self._extract_topic(query)
        self.voice_evolution.record_interaction(topic, feedback)
        
        # Evolve personality based on interaction
        if feedback:
            self._evolve_from_feedback(feedback)
        
        return styled_response
    
    def _calculate_emotion_intensity(self, text: str) -> float:
        """Calculate emotional intensity from text"""
        # Simple heuristic: punctuation and capitalization
        exclamations = text.count('!')
        questions = text.count('?')
        caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
        
        intensity = 0.5  # Base
        intensity += min(exclamations * 0.1, 0.3)
        intensity += min(questions * 0.05, 0.2)
        intensity += min(caps_ratio * 0.5, 0.3)
        
        return np.clip(intensity, 0.0, 1.0)
    
    def _extract_topic(self, text: str) -> str:
        """Extract main topic from text (simplified)"""
        # In production, use NLP/topic modeling
        words = text.lower().split()
        # Filter common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'}
        keywords = [w for w in words if w not in stop_words and len(w) > 3]
        return keywords[0] if keywords else 'general'
    
    def _evolve_from_feedback(self, feedback: str):
        """Evolve personality traits based on feedback"""
        feedback_lower = feedback.lower()
        
        experience_impact = {}
        
        if 'creative' in feedback_lower or 'innovative' in feedback_lower:
            experience_impact['creativity'] = 0.05
        
        if 'careful' in feedback_lower or 'thorough' in feedback_lower:
            experience_impact['caution'] = 0.05
        
        if 'funny' in feedback_lower or 'humor' in feedback_lower:
            experience_impact['humor'] = 0.05
        
        if 'understanding' in feedback_lower or 'empathetic' in feedback_lower:
            experience_impact['empathy'] = 0.05
        
        if experience_impact:
            self.traits.evolve(experience_impact)
    
    def get_personality_summary(self) -> Dict[str, Any]:
        """Get comprehensive personality summary"""
        return {
            'personality_id': self.personality_id,
            'created_at': self.created_at,
            'age_seconds': datetime.now().timestamp() - self.created_at,
            'traits': self.traits.to_dict(),
            'emotional_state': self.emotional_state.get_stats(),
            'voice_evolution': self.voice_evolution.get_stats(),
            'dominant_traits': self._get_dominant_traits()
        }
    
    def _get_dominant_traits(self) -> List[Tuple[str, float]]:
        """Get top 3 dominant traits"""
        traits_dict = self.traits.to_dict()
        sorted_traits = sorted(traits_dict.items(), key=lambda x: x[1], reverse=True)
        return sorted_traits[:3]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for monitoring"""
        return self.get_personality_summary()


# Convenience function
def create_personality(traits: Optional[PersonalityTraits] = None) -> PersonalityEngine:
    """Create a personality engine with optional custom traits"""
    return PersonalityEngine(traits)
