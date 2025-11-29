"""
Self-Learning System - Week 4
==============================
Enable the brain to remember, learn, and improve continuously.

This module enables the brain to:
- Remember every interaction (episodic memory)
- Build knowledge graphs (semantic memory)
- Learn and improve skills (procedural memory)
- Learn how to learn better (meta-learning)

The brain becomes a continuously evolving learning system.
"""

import numpy as np
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import json
import pickle


@dataclass
class Episode:
    """
    Single interaction episode.
    Stored in episodic memory.
    """
    episode_id: str
    timestamp: float
    query: str
    response: str
    context: Dict[str, Any]
    outcome: Dict[str, Any]  # success, user_feedback, etc.
    emotions: str = "neutral"
    learned_from: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'episode_id': self.episode_id,
            'timestamp': self.timestamp,
            'query': self.query,
            'response': self.response[:200],  # Truncate for storage
            'context': self.context,
            'outcome': self.outcome,
            'emotions': self.emotions,
            'learned_from': self.learned_from
        }


class EpisodicMemory:
    """
    Stores every interaction as episodes.
    Enables learning from past experiences.
    """
    
    def __init__(self, max_episodes: int = 10000):
        self.max_episodes = max_episodes
        self.episodes: List[Episode] = []
        self.episode_count = 0
    
    def store_episode(self, query: str, response: str, 
                     context: Dict[str, Any], outcome: Dict[str, Any],
                     emotions: str = "neutral") -> Episode:
        """Store a new episode"""
        episode = Episode(
            episode_id=f"ep_{self.episode_count:06d}",
            timestamp=datetime.now().timestamp(),
            query=query,
            response=response,
            context=context,
            outcome=outcome,
            emotions=emotions
        )
        
        self.episodes.append(episode)
        self.episode_count += 1
        
        # Remove oldest if exceeding limit
        if len(self.episodes) > self.max_episodes:
            self.episodes.pop(0)
        
        return episode
    
    def recall_similar(self, query: str, top_k: int = 5) -> List[Episode]:
        """
        Recall similar past episodes.
        Simple keyword-based similarity for now.
        """
        query_words = set(query.lower().split())
        
        # Score episodes by word overlap
        scored_episodes = []
        for episode in self.episodes:
            episode_words = set(episode.query.lower().split())
            overlap = len(query_words.intersection(episode_words))
            if overlap > 0:
                scored_episodes.append((episode, overlap))
        
        # Sort by score
        scored_episodes.sort(key=lambda x: x[1], reverse=True)
        
        return [ep for ep, _ in scored_episodes[:top_k]]
    
    def recall_successful(self, task_type: Optional[str] = None, 
                         top_k: int = 10) -> List[Episode]:
        """Recall successful episodes"""
        successful = [
            ep for ep in self.episodes
            if ep.outcome.get('success', False)
        ]
        
        # Filter by task type if specified
        if task_type:
            successful = [
                ep for ep in successful
                if ep.context.get('task_type') == task_type
            ]
        
        # Return most recent
        return successful[-top_k:]
    
    def recall_failures(self, top_k: int = 10) -> List[Episode]:
        """Recall failed episodes to learn from mistakes"""
        failures = [
            ep for ep in self.episodes
            if not ep.outcome.get('success', True)
        ]
        return failures[-top_k:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get episodic memory statistics"""
        if not self.episodes:
            return {
                'total_episodes': 0,
                'success_rate': 0.0,
                'memory_usage': 0
            }
        
        successes = sum(1 for ep in self.episodes if ep.outcome.get('success', False))
        
        return {
            'total_episodes': len(self.episodes),
            'success_rate': successes / len(self.episodes) if self.episodes else 0.0,
            'memory_usage': len(self.episodes),
            'oldest_episode': self.episodes[0].timestamp if self.episodes else None,
            'newest_episode': self.episodes[-1].timestamp if self.episodes else None
        }


@dataclass
class ConceptNode:
    """Node in the knowledge graph"""
    concept_id: str
    name: str
    description: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    access_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'concept_id': self.concept_id,
            'name': self.name,
            'description': self.description,
            'properties': self.properties,
            'access_count': self.access_count
        }


@dataclass
class ConceptRelation:
    """Edge in the knowledge graph"""
    relation_id: str
    source_id: str
    target_id: str
    relation_type: str  # 'is_a', 'part_of', 'related_to', 'causes', etc.
    strength: float = 1.0
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())


class SemanticMemory:
    """
    Knowledge graph of concepts and relationships.
    Builds understanding over time.
    """
    
    def __init__(self):
        self.concepts: Dict[str, ConceptNode] = {}
        self.relations: List[ConceptRelation] = []
        self.concept_count = 0
        self.relation_count = 0
    
    def add_concept(self, name: str, description: str = "",
                   properties: Optional[Dict[str, Any]] = None) -> ConceptNode:
        """Add a new concept to knowledge graph"""
        concept_id = f"concept_{self.concept_count:06d}"
        
        concept = ConceptNode(
            concept_id=concept_id,
            name=name,
            description=description,
            properties=properties or {}
        )
        
        self.concepts[concept_id] = concept
        self.concept_count += 1
        
        return concept
    
    def add_relation(self, source_name: str, target_name: str,
                    relation_type: str, strength: float = 1.0):
        """Add relationship between concepts"""
        # Find or create concepts
        source = self._find_or_create_concept(source_name)
        target = self._find_or_create_concept(target_name)
        
        relation = ConceptRelation(
            relation_id=f"rel_{self.relation_count:06d}",
            source_id=source.concept_id,
            target_id=target.concept_id,
            relation_type=relation_type,
            strength=strength
        )
        
        self.relations.append(relation)
        self.relation_count += 1
        
        return relation
    
    def _find_or_create_concept(self, name: str) -> ConceptNode:
        """Find existing concept or create new one"""
        # Try to find existing
        for concept in self.concepts.values():
            if concept.name.lower() == name.lower():
                concept.access_count += 1
                return concept
        
        # Create new
        return self.add_concept(name)
    
    def get_related_concepts(self, concept_name: str, 
                           max_depth: int = 2) -> List[ConceptNode]:
        """Get concepts related to given concept"""
        concept = self._find_or_create_concept(concept_name)
        
        related_ids = set()
        current_ids = {concept.concept_id}
        
        # BFS traversal
        for _ in range(max_depth):
            next_ids = set()
            for rel in self.relations:
                if rel.source_id in current_ids:
                    next_ids.add(rel.target_id)
                    related_ids.add(rel.target_id)
                elif rel.target_id in current_ids:
                    next_ids.add(rel.source_id)
                    related_ids.add(rel.source_id)
            current_ids = next_ids
            if not current_ids:
                break
        
        return [self.concepts[cid] for cid in related_ids if cid in self.concepts]
    
    def learn_from_text(self, text: str):
        """
        Extract concepts from text and add to knowledge graph.
        Simple implementation - just extracts noun phrases.
        """
        # Simple extraction: capitalize words as potential concepts
        words = text.split()
        potential_concepts = [w for w in words if len(w) > 3 and w[0].isupper()]
        
        # Add concepts
        for concept_name in potential_concepts:
            self._find_or_create_concept(concept_name)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get semantic memory statistics"""
        return {
            'total_concepts': len(self.concepts),
            'total_relations': len(self.relations),
            'avg_connections_per_concept': len(self.relations) / len(self.concepts) if self.concepts else 0,
            'most_accessed_concepts': sorted(
                [(c.name, c.access_count) for c in self.concepts.values()],
                key=lambda x: x[1],
                reverse=True
            )[:5]
        }


@dataclass
class Skill:
    """Learned procedural skill"""
    skill_id: str
    name: str
    description: str
    proficiency: float = 0.0  # 0.0 to 1.0
    practice_count: int = 0
    success_count: int = 0
    last_practiced: float = field(default_factory=lambda: datetime.now().timestamp())
    learning_curve: List[float] = field(default_factory=list)
    
    def practice(self, success: bool):
        """Practice the skill"""
        self.practice_count += 1
        if success:
            self.success_count += 1
        
        # Update proficiency (moving average)
        success_rate = self.success_count / self.practice_count
        self.proficiency = 0.7 * self.proficiency + 0.3 * success_rate
        self.learning_curve.append(self.proficiency)
        self.last_practiced = datetime.now().timestamp()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'skill_id': self.skill_id,
            'name': self.name,
            'proficiency': self.proficiency,
            'practice_count': self.practice_count,
            'success_rate': self.success_count / self.practice_count if self.practice_count > 0 else 0
        }


class ProceduralMemory:
    """
    Stores learned skills and procedures.
    Tracks proficiency and improvement.
    """
    
    def __init__(self):
        self.skills: Dict[str, Skill] = {}
        self.skill_count = 0
    
    def learn_skill(self, name: str, description: str = "") -> Skill:
        """Start learning a new skill"""
        skill_id = f"skill_{self.skill_count:06d}"
        
        skill = Skill(
            skill_id=skill_id,
            name=name,
            description=description
        )
        
        self.skills[skill_id] = skill
        self.skill_count += 1
        
        return skill
    
    def practice_skill(self, skill_name: str, success: bool):
        """Practice a skill"""
        # Find skill
        skill = self._find_skill(skill_name)
        if skill:
            skill.practice(success)
        else:
            # Learn new skill
            skill = self.learn_skill(skill_name)
            skill.practice(success)
    
    def _find_skill(self, name: str) -> Optional[Skill]:
        """Find skill by name"""
        for skill in self.skills.values():
            if skill.name.lower() == name.lower():
                return skill
        return None
    
    def get_proficiency(self, skill_name: str) -> float:
        """Get proficiency level for a skill"""
        skill = self._find_skill(skill_name)
        return skill.proficiency if skill else 0.0
    
    def get_mastered_skills(self, threshold: float = 0.8) -> List[Skill]:
        """Get skills above proficiency threshold"""
        return [
            skill for skill in self.skills.values()
            if skill.proficiency >= threshold
        ]
    
    def get_learning_skills(self, threshold: float = 0.8) -> List[Skill]:
        """Get skills still being learned"""
        return [
            skill for skill in self.skills.values()
            if skill.proficiency < threshold and skill.practice_count > 0
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get procedural memory statistics"""
        mastered = len(self.get_mastered_skills())
        learning = len(self.get_learning_skills())
        
        return {
            'total_skills': len(self.skills),
            'mastered_skills': mastered,
            'learning_skills': learning,
            'avg_proficiency': np.mean([s.proficiency for s in self.skills.values()]) if self.skills else 0.0,
            'top_skills': sorted(
                [(s.name, s.proficiency) for s in self.skills.values()],
                key=lambda x: x[1],
                reverse=True
            )[:5]
        }


@dataclass
class LearningStrategy:
    """Meta-learning strategy"""
    strategy_id: str
    name: str
    description: str
    success_count: int = 0
    failure_count: int = 0
    avg_performance: float = 0.5
    contexts_used: List[str] = field(default_factory=list)
    
    def update(self, success: bool, performance: float):
        """Update strategy based on outcome"""
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        
        # Update average performance (moving average)
        total = self.success_count + self.failure_count
        self.avg_performance = ((total - 1) * self.avg_performance + performance) / total
    
    def get_success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0


class MetaLearner:
    """
    Learns how to learn better.
    Optimizes learning strategies based on outcomes.
    """
    
    def __init__(self):
        self.strategies: Dict[str, LearningStrategy] = {}
        self.strategy_count = 0
        
        # Initialize default strategies
        self._initialize_default_strategies()
    
    def _initialize_default_strategies(self):
        """Create default learning strategies"""
        default_strategies = [
            ("repetition", "Learn through repeated practice"),
            ("analogy", "Learn by comparing to known concepts"),
            ("decomposition", "Break complex tasks into simpler parts"),
            ("experimentation", "Learn through trial and error"),
            ("pattern_recognition", "Identify patterns in data"),
            ("feedback_integration", "Learn from feedback")
        ]
        
        for name, description in default_strategies:
            self.add_strategy(name, description)
    
    def add_strategy(self, name: str, description: str) -> LearningStrategy:
        """Add a new learning strategy"""
        strategy_id = f"strategy_{self.strategy_count:06d}"
        
        strategy = LearningStrategy(
            strategy_id=strategy_id,
            name=name,
            description=description
        )
        
        self.strategies[strategy_id] = strategy
        self.strategy_count += 1
        
        return strategy
    
    def select_strategy(self, context: Dict[str, Any]) -> LearningStrategy:
        """
        Select best learning strategy for context.
        Uses epsilon-greedy: exploit best or explore random.
        """
        epsilon = 0.2  # 20% exploration
        
        if np.random.random() < epsilon or not self.strategies:
            # Explore: random strategy
            return np.random.choice(list(self.strategies.values()))
        else:
            # Exploit: best performing strategy
            best = max(self.strategies.values(), 
                      key=lambda s: s.avg_performance)
            return best
    
    def update_strategy(self, strategy_id: str, success: bool, 
                       performance: float, context: Dict[str, Any]):
        """Update strategy based on outcome"""
        if strategy_id in self.strategies:
            strategy = self.strategies[strategy_id]
            strategy.update(success, performance)
            strategy.contexts_used.append(context.get('task_type', 'unknown'))
    
    def get_best_strategies(self, top_k: int = 3) -> List[LearningStrategy]:
        """Get top performing strategies"""
        sorted_strategies = sorted(
            self.strategies.values(),
            key=lambda s: s.avg_performance,
            reverse=True
        )
        return sorted_strategies[:top_k]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get meta-learning statistics"""
        if not self.strategies:
            return {'total_strategies': 0}
        
        return {
            'total_strategies': len(self.strategies),
            'best_strategies': [
                (s.name, s.avg_performance, s.get_success_rate())
                for s in self.get_best_strategies(3)
            ],
            'avg_strategy_performance': np.mean([s.avg_performance for s in self.strategies.values()])
        }


class SelfLearningSystem:
    """
    Main orchestrator for self-learning.
    Integrates all memory systems and meta-learning.
    """
    
    def __init__(self):
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
        self.procedural = ProceduralMemory()
        self.meta_learner = MetaLearner()
        
        self.total_learning_cycles = 0
    
    def learn_from_interaction(self, query: str, response: str,
                               context: Dict[str, Any], 
                               outcome: Dict[str, Any],
                               emotions: str = "neutral"):
        """
        Learn from a single interaction.
        Updates all memory systems.
        """
        
        # 1. Store episode
        episode = self.episodic.store_episode(
            query, response, context, outcome, emotions
        )
        
        # 2. Extract concepts for semantic memory
        self.semantic.learn_from_text(query)
        self.semantic.learn_from_text(response)
        
        # 3. Update procedural memory
        task_type = context.get('task_type', 'general')
        success = outcome.get('success', False)
        self.procedural.practice_skill(task_type, success)
        
        # 4. Update meta-learning
        strategy_id = context.get('learning_strategy_id')
        if strategy_id:
            performance = outcome.get('performance', 0.5)
            self.meta_learner.update_strategy(
                strategy_id, success, performance, context
            )
        
        self.total_learning_cycles += 1
    
    def recall_relevant_knowledge(self, query: str) -> Dict[str, Any]:
        """
        Recall relevant knowledge from all memory systems.
        """
        
        # Get similar episodes
        similar_episodes = self.episodic.recall_similar(query, top_k=3)
        
        # Get related concepts (extract key terms from query)
        query_words = [w for w in query.split() if len(w) > 3]
        related_concepts = []
        for word in query_words[:3]:  # Check first 3 meaningful words
            related = self.semantic.get_related_concepts(word, max_depth=1)
            related_concepts.extend(related)
        
        # Get relevant skills
        task_type = self._infer_task_type(query)
        skill_proficiency = self.procedural.get_proficiency(task_type)
        
        # Get best learning strategy
        best_strategy = self.meta_learner.select_strategy({
            'task_type': task_type,
            'query': query
        })
        
        return {
            'similar_episodes': [ep.to_dict() for ep in similar_episodes],
            'related_concepts': [c.to_dict() for c in related_concepts[:5]],
            'skill_proficiency': skill_proficiency,
            'recommended_strategy': {
                'name': best_strategy.name,
                'description': best_strategy.description,
                'strategy_id': best_strategy.strategy_id
            }
        }
    
    def _infer_task_type(self, query: str) -> str:
        """Infer task type from query"""
        query_lower = query.lower()
        
        if any(w in query_lower for w in ['code', 'program', 'function', 'debug']):
            return 'coding'
        elif any(w in query_lower for w in ['create', 'design', 'imagine', 'invent']):
            return 'creative'
        elif any(w in query_lower for w in ['why', 'how', 'explain', 'reason']):
            return 'reasoning'
        elif any(w in query_lower for w in ['analyze', 'compare', 'evaluate']):
            return 'analytical'
        else:
            return 'general'
    
    def get_learning_progress(self) -> Dict[str, Any]:
        """Get comprehensive learning progress"""
        return {
            'total_learning_cycles': self.total_learning_cycles,
            'episodic_memory': self.episodic.get_stats(),
            'semantic_memory': self.semantic.get_stats(),
            'procedural_memory': self.procedural.get_stats(),
            'meta_learning': self.meta_learner.get_stats()
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get all statistics"""
        return self.get_learning_progress()


# Convenience function
def create_self_learning_system() -> SelfLearningSystem:
    """Create self-learning system"""
    return SelfLearningSystem()
