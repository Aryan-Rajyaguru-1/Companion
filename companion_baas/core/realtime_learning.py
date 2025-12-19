#!/usr/bin/env python3
"""
Real-time Learning System
=========================

Enables continuous learning from user interactions:
- Feedback collection and processing
- Pattern recognition and analysis
- Preference tracking and adaptation
- Response quality improvement
- Behavioral adaptation
"""

import logging
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, Counter
import statistics

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    """Types of user feedback"""
    POSITIVE = "positive"          # Thumbs up, like
    NEGATIVE = "negative"          # Thumbs down, dislike
    CORRECTION = "correction"      # User corrects response
    RATING = "rating"             # Numerical rating
    PREFERENCE = "preference"      # User preference indication
    COMMENT = "comment"           # Text feedback


class LearningSignal(Enum):
    """Signals for learning"""
    USER_CORRECTION = "user_correction"
    REPEATED_QUESTION = "repeated_question"
    FOLLOW_UP = "follow_up"
    EXPLICIT_FEEDBACK = "explicit_feedback"
    IMPLICIT_SATISFACTION = "implicit_satisfaction"
    TASK_COMPLETION = "task_completion"
    ERROR_OCCURRED = "error_occurred"


@dataclass
class FeedbackEntry:
    """Single feedback entry"""
    id: str
    user_id: str
    interaction_id: str
    feedback_type: FeedbackType
    value: Any  # Rating, corrected text, comment, etc.
    context: Dict[str, Any]
    timestamp: float
    processed: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "interaction_id": self.interaction_id,
            "feedback_type": self.feedback_type.value,
            "value": self.value,
            "context": self.context,
            "timestamp": self.timestamp,
            "processed": self.processed
        }


@dataclass
class Pattern:
    """Learned pattern"""
    id: str
    pattern_type: str
    description: str
    occurrences: int
    confidence: float  # 0.0 to 1.0
    first_seen: float
    last_seen: float
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "pattern_type": self.pattern_type,
            "description": self.description,
            "occurrences": self.occurrences,
            "confidence": self.confidence,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "metadata": self.metadata
        }


@dataclass
class UserPreference:
    """User preference"""
    user_id: str
    category: str
    preference: str
    strength: float  # 0.0 to 1.0
    learned_from: int  # Number of interactions
    last_updated: float


class FeedbackCollector:
    """Collect and store user feedback"""
    
    def __init__(self):
        self.feedback: Dict[str, FeedbackEntry] = {}
        self.feedback_counter = 0
    
    def add_feedback(
        self,
        user_id: str,
        interaction_id: str,
        feedback_type: FeedbackType,
        value: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> FeedbackEntry:
        """
        Add new feedback
        
        Args:
            user_id: User identifier
            interaction_id: Related interaction ID
            feedback_type: Type of feedback
            value: Feedback value
            context: Additional context
            
        Returns:
            Created FeedbackEntry
        """
        self.feedback_counter += 1
        feedback_id = f"feedback_{self.feedback_counter}_{int(time.time())}"
        
        entry = FeedbackEntry(
            id=feedback_id,
            user_id=user_id,
            interaction_id=interaction_id,
            feedback_type=feedback_type,
            value=value,
            context=context or {},
            timestamp=time.time()
        )
        
        self.feedback[feedback_id] = entry
        logger.info(f"Feedback collected: {feedback_type.value} from {user_id}")
        return entry
    
    def get_unprocessed(self, limit: int = 100) -> List[FeedbackEntry]:
        """Get unprocessed feedback"""
        unprocessed = [f for f in self.feedback.values() if not f.processed]
        unprocessed.sort(key=lambda f: f.timestamp)
        return unprocessed[:limit]
    
    def mark_processed(self, feedback_id: str):
        """Mark feedback as processed"""
        if feedback_id in self.feedback:
            self.feedback[feedback_id].processed = True
    
    def get_user_feedback(
        self,
        user_id: str,
        feedback_type: Optional[FeedbackType] = None,
        limit: int = 50
    ) -> List[FeedbackEntry]:
        """Get feedback for specific user"""
        user_feedback = [f for f in self.feedback.values() if f.user_id == user_id]
        
        if feedback_type:
            user_feedback = [f for f in user_feedback if f.feedback_type == feedback_type]
        
        user_feedback.sort(key=lambda f: f.timestamp, reverse=True)
        return user_feedback[:limit]


class PatternRecognizer:
    """Recognize patterns in user interactions"""
    
    def __init__(self):
        self.patterns: Dict[str, Pattern] = {}
        self.pattern_counter = 0
        
        # Track sequences
        self.user_sequences: Dict[str, List[str]] = defaultdict(list)
        self.query_frequency: Dict[str, int] = Counter()
    
    def track_interaction(
        self,
        user_id: str,
        query: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Track interaction for pattern recognition"""
        # Track query frequency
        query_lower = query.lower().strip()
        self.query_frequency[query_lower] += 1
        
        # Track user sequences
        self.user_sequences[user_id].append(query_lower)
        
        # Keep sequences manageable
        if len(self.user_sequences[user_id]) > 100:
            self.user_sequences[user_id].pop(0)
        
        # Check for repeated questions
        if self.query_frequency[query_lower] >= 3:
            self._create_pattern(
                pattern_type="repeated_query",
                description=f"Frequently asked: {query}",
                confidence=min(self.query_frequency[query_lower] / 10.0, 1.0),
                metadata={"query": query, "count": self.query_frequency[query_lower]}
            )
    
    def detect_patterns(self) -> List[Pattern]:
        """Detect patterns from tracked data"""
        detected = []
        
        # Find common sequences
        for user_id, sequence in self.user_sequences.items():
            if len(sequence) < 3:
                continue
            
            # Look for repeating patterns
            for length in [2, 3]:
                for i in range(len(sequence) - length):
                    subseq = tuple(sequence[i:i+length])
                    
                    # Count occurrences
                    count = 0
                    for j in range(len(sequence) - length):
                        if tuple(sequence[j:j+length]) == subseq:
                            count += 1
                    
                    if count >= 2:
                        pattern = self._create_pattern(
                            pattern_type="query_sequence",
                            description=f"Common sequence: {' → '.join(subseq)}",
                            confidence=min(count / 5.0, 1.0),
                            metadata={
                                "sequence": list(subseq),
                                "user_id": user_id,
                                "occurrences": count
                            }
                        )
                        detected.append(pattern)
        
        return detected
    
    def _create_pattern(
        self,
        pattern_type: str,
        description: str,
        confidence: float,
        metadata: Dict[str, Any]
    ) -> Pattern:
        """Create or update pattern"""
        # Check if pattern already exists
        for pattern in self.patterns.values():
            if pattern.pattern_type == pattern_type and pattern.description == description:
                pattern.occurrences += 1
                pattern.confidence = min(pattern.confidence + 0.1, 1.0)
                pattern.last_seen = time.time()
                return pattern
        
        # Create new pattern
        self.pattern_counter += 1
        pattern_id = f"pattern_{self.pattern_counter}"
        
        pattern = Pattern(
            id=pattern_id,
            pattern_type=pattern_type,
            description=description,
            occurrences=1,
            confidence=confidence,
            first_seen=time.time(),
            last_seen=time.time(),
            metadata=metadata
        )
        
        self.patterns[pattern_id] = pattern
        logger.info(f"Pattern detected: {description}")
        return pattern
    
    def get_patterns(
        self,
        pattern_type: Optional[str] = None,
        min_confidence: float = 0.5
    ) -> List[Pattern]:
        """Get recognized patterns"""
        patterns = list(self.patterns.values())
        
        if pattern_type:
            patterns = [p for p in patterns if p.pattern_type == pattern_type]
        
        patterns = [p for p in patterns if p.confidence >= min_confidence]
        patterns.sort(key=lambda p: p.confidence, reverse=True)
        
        return patterns


class PreferenceTracker:
    """Track and learn user preferences"""
    
    def __init__(self):
        self.preferences: Dict[str, Dict[str, UserPreference]] = defaultdict(dict)
    
    def record_preference(
        self,
        user_id: str,
        category: str,
        preference: str,
        strength: float = 0.5
    ):
        """
        Record user preference
        
        Args:
            user_id: User identifier
            category: Preference category (e.g., 'response_style', 'language')
            preference: Preference value
            strength: Preference strength (0.0-1.0)
        """
        key = f"{category}:{preference}"
        
        if key in self.preferences[user_id]:
            # Update existing
            pref = self.preferences[user_id][key]
            pref.strength = min(pref.strength + 0.1, 1.0)
            pref.learned_from += 1
            pref.last_updated = time.time()
        else:
            # Create new
            pref = UserPreference(
                user_id=user_id,
                category=category,
                preference=preference,
                strength=strength,
                learned_from=1,
                last_updated=time.time()
            )
            self.preferences[user_id][key] = pref
        
        logger.info(f"Preference learned: {user_id} prefers {preference} for {category}")
    
    def get_preference(
        self,
        user_id: str,
        category: str
    ) -> Optional[str]:
        """
        Get user's preference for category
        
        Args:
            user_id: User identifier
            category: Preference category
            
        Returns:
            Preferred value or None
        """
        user_prefs = self.preferences.get(user_id, {})
        category_prefs = [p for p in user_prefs.values() if p.category == category]
        
        if not category_prefs:
            return None
        
        # Return strongest preference
        category_prefs.sort(key=lambda p: p.strength, reverse=True)
        return category_prefs[0].preference
    
    def get_all_preferences(self, user_id: str) -> Dict[str, str]:
        """Get all preferences for user"""
        user_prefs = self.preferences.get(user_id, {})
        
        # Group by category, keep strongest
        by_category = defaultdict(list)
        for pref in user_prefs.values():
            by_category[pref.category].append(pref)
        
        result = {}
        for category, prefs in by_category.items():
            prefs.sort(key=lambda p: p.strength, reverse=True)
            result[category] = prefs[0].preference
        
        return result


class QualityAnalyzer:
    """Analyze response quality and suggest improvements"""
    
    def __init__(self):
        self.response_scores: Dict[str, List[float]] = defaultdict(list)
        self.error_tracking: Dict[str, int] = Counter()
    
    def record_score(
        self,
        interaction_id: str,
        score: float,
        category: str = "overall"
    ):
        """Record quality score"""
        self.response_scores[category].append(score)
        
        # Keep limited history
        if len(self.response_scores[category]) > 1000:
            self.response_scores[category].pop(0)
    
    def get_average_quality(self, category: str = "overall") -> float:
        """Get average quality score"""
        scores = self.response_scores.get(category, [])
        if not scores:
            return 0.5  # Default neutral
        return statistics.mean(scores)
    
    def get_trend(self, category: str = "overall", window: int = 50) -> str:
        """
        Analyze quality trend
        
        Returns:
            'improving', 'declining', or 'stable'
        """
        scores = self.response_scores.get(category, [])
        if len(scores) < window * 2:
            return "stable"
        
        recent = scores[-window:]
        previous = scores[-window*2:-window]
        
        recent_avg = statistics.mean(recent)
        previous_avg = statistics.mean(previous)
        
        diff = recent_avg - previous_avg
        
        if diff > 0.05:
            return "improving"
        elif diff < -0.05:
            return "declining"
        else:
            return "stable"
    
    def record_error(self, error_type: str):
        """Record error occurrence"""
        self.error_tracking[error_type] += 1
    
    def get_common_errors(self, top_n: int = 5) -> List[Tuple[str, int]]:
        """Get most common errors"""
        return self.error_tracking.most_common(top_n)


class AdaptationEngine:
    """Adapt behavior based on learning"""
    
    def __init__(self):
        self.adaptations: Dict[str, Any] = {}
        
    def suggest_adaptations(
        self,
        patterns: List[Pattern],
        preferences: Dict[str, str],
        quality_trend: str
    ) -> List[str]:
        """
        Suggest adaptations based on learned data
        
        Args:
            patterns: Recognized patterns
            preferences: User preferences
            quality_trend: Quality trend
            
        Returns:
            List of adaptation suggestions
        """
        suggestions = []
        
        # Adapt to patterns
        for pattern in patterns:
            if pattern.pattern_type == "repeated_query" and pattern.confidence > 0.7:
                suggestions.append(
                    f"Cache response for: {pattern.metadata.get('query', 'query')}"
                )
            
            elif pattern.pattern_type == "query_sequence":
                suggestions.append(
                    f"Anticipate follow-up questions in sequence: {pattern.description}"
                )
        
        # Adapt to preferences
        for category, preference in preferences.items():
            suggestions.append(f"Apply {category} preference: {preference}")
        
        # Adapt to quality trend
        if quality_trend == "declining":
            suggestions.append("Review recent responses for quality issues")
            suggestions.append("Consider adjusting response generation parameters")
        
        return suggestions
    
    def apply_adaptation(self, adaptation_id: str, config: Dict[str, Any]):
        """Apply an adaptation"""
        self.adaptations[adaptation_id] = config
        logger.info(f"Applied adaptation: {adaptation_id}")
    
    def get_active_adaptations(self) -> Dict[str, Any]:
        """Get currently active adaptations"""
        return self.adaptations.copy()


class RealtimeLearningSystem:
    """
    Unified Real-time Learning System
    Continuously learns and adapts from interactions
    """
    
    def __init__(self):
        self.feedback_collector = FeedbackCollector()
        self.pattern_recognizer = PatternRecognizer()
        self.preference_tracker = PreferenceTracker()
        self.quality_analyzer = QualityAnalyzer()
        self.adaptation_engine = AdaptationEngine()
        
        self.enabled = True
        logger.info("✅ Real-time Learning System initialized")
    
    def provide_feedback(
        self,
        user_id: str,
        interaction_id: str,
        feedback_type: str,
        value: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> FeedbackEntry:
        """
        Submit user feedback
        
        Args:
            user_id: User identifier
            interaction_id: Related interaction
            feedback_type: Type of feedback
            value: Feedback value
            context: Additional context
            
        Returns:
            FeedbackEntry
        """
        fb_type = FeedbackType(feedback_type)
        entry = self.feedback_collector.add_feedback(
            user_id, interaction_id, fb_type, value, context
        )
        
        # Process feedback immediately
        self._process_feedback(entry)
        
        return entry
    
    def track_interaction(
        self,
        user_id: str,
        query: str,
        response: str,
        score: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Track interaction for learning
        
        Args:
            user_id: User identifier
            query: User query
            response: System response
            score: Quality score (optional)
            metadata: Additional metadata
        """
        # Pattern recognition
        self.pattern_recognizer.track_interaction(user_id, query, response, metadata)
        
        # Quality tracking
        if score is not None:
            interaction_id = f"int_{int(time.time())}"
            self.quality_analyzer.record_score(interaction_id, score)
        
        # Learn preferences from metadata
        if metadata:
            if "preferred_style" in metadata:
                self.preference_tracker.record_preference(
                    user_id, "response_style", metadata["preferred_style"]
                )
    
    def learn_preference(
        self,
        user_id: str,
        category: str,
        preference: str,
        strength: float = 0.5
    ):
        """
        Learn user preference
        
        Args:
            user_id: User identifier
            category: Preference category
            preference: Preference value
            strength: Preference strength
        """
        self.preference_tracker.record_preference(
            user_id, category, preference, strength
        )
    
    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """
        Get learned user profile
        
        Args:
            user_id: User identifier
            
        Returns:
            User profile with preferences and patterns
        """
        preferences = self.preference_tracker.get_all_preferences(user_id)
        feedback_stats = self._calculate_feedback_stats(user_id)
        
        return {
            "user_id": user_id,
            "preferences": preferences,
            "feedback_stats": feedback_stats,
            "quality_trend": self.quality_analyzer.get_trend()
        }
    
    def get_adaptations(self) -> List[str]:
        """
        Get current adaptation suggestions
        
        Returns:
            List of adaptation suggestions
        """
        patterns = self.pattern_recognizer.get_patterns(min_confidence=0.6)
        quality_trend = self.quality_analyzer.get_trend()
        
        # Get preferences (aggregate across users for now)
        all_prefs = {}
        
        suggestions = self.adaptation_engine.suggest_adaptations(
            patterns, all_prefs, quality_trend
        )
        
        return suggestions
    
    def _process_feedback(self, feedback: FeedbackEntry):
        """Process feedback entry"""
        user_id = feedback.user_id
        
        # Learn from different feedback types
        if feedback.feedback_type == FeedbackType.RATING:
            score = float(feedback.value)
            self.quality_analyzer.record_score(
                feedback.interaction_id,
                score / 5.0  # Normalize to 0-1
            )
        
        elif feedback.feedback_type == FeedbackType.PREFERENCE:
            if "category" in feedback.context and "preference" in feedback.context:
                self.preference_tracker.record_preference(
                    user_id,
                    feedback.context["category"],
                    feedback.context["preference"]
                )
        
        elif feedback.feedback_type == FeedbackType.CORRECTION:
            # Learn from corrections
            logger.info(f"User correction received: {feedback.value}")
        
        self.feedback_collector.mark_processed(feedback.id)
    
    def _calculate_feedback_stats(self, user_id: str) -> Dict[str, Any]:
        """Calculate feedback statistics for user"""
        feedback = self.feedback_collector.get_user_feedback(user_id)
        
        if not feedback:
            return {"total": 0}
        
        by_type = defaultdict(int)
        for fb in feedback:
            by_type[fb.feedback_type.value] += 1
        
        return {
            "total": len(feedback),
            "by_type": dict(by_type),
            "positive_ratio": by_type["positive"] / len(feedback) if feedback else 0
        }


# Convenience function
def create_learning_system() -> RealtimeLearningSystem:
    """Create real-time learning system"""
    return RealtimeLearningSystem()
