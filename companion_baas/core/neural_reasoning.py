"""
Neural Reasoning Engine - Week 2
=================================
Transform simple prompt→response into true multi-step reasoning.

This module enables the brain to:
- Think in vectors (semantic representations)
- Use chain-of-thought (internal dialogue)
- Form abstract concepts
- Synthesize creative solutions

Not just: prompt → model → response
But: prompt → internal reasoning → concepts → synthesis → response
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
from sentence_transformers import SentenceTransformer


@dataclass
class ThoughtVector:
    """
    Vector representation of a thought/concept.
    Thoughts are semantic embeddings that can be manipulated mathematically.
    """
    content: str
    vector: np.ndarray
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    confidence: float = 1.0
    source: str = "reasoning"
    
    def similarity(self, other: 'ThoughtVector') -> float:
        """Calculate semantic similarity with another thought"""
        return float(np.dot(self.vector, other.vector) / 
                    (np.linalg.norm(self.vector) * np.linalg.norm(other.vector)))
    
    def combine(self, other: 'ThoughtVector', weight: float = 0.5) -> 'ThoughtVector':
        """Combine two thoughts into a new thought"""
        new_vector = weight * self.vector + (1 - weight) * other.vector
        new_content = f"[{self.content}] + [{other.content}]"
        return ThoughtVector(
            content=new_content,
            vector=new_vector,
            confidence=min(self.confidence, other.confidence),
            source="synthesis"
        )


class ThoughtSpace:
    """
    Vector space for thoughts. All thinking happens here.
    Uses sentence-transformers for semantic embeddings.
    """
    
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        try:
            self.model = SentenceTransformer(model_name)
            self.enabled = True
        except Exception as e:
            print(f"⚠️ ThoughtSpace: sentence-transformers not available: {e}")
            self.enabled = False
            self.model = None
        
        self.thought_history: List[ThoughtVector] = []
    
    def encode_thought(self, text: str, source: str = "reasoning") -> Optional[ThoughtVector]:
        """Convert text into a thought vector"""
        if not self.enabled:
            return None
        
        try:
            vector = self.model.encode(text, convert_to_numpy=True)
            thought = ThoughtVector(
                content=text,
                vector=vector,
                source=source
            )
            self.thought_history.append(thought)
            return thought
        except Exception as e:
            print(f"⚠️ Failed to encode thought: {e}")
            return None
    
    def find_similar_thoughts(self, query_thought: ThoughtVector, 
                             top_k: int = 5) -> List[Tuple[ThoughtVector, float]]:
        """Find similar thoughts from history"""
        similarities = []
        for thought in self.thought_history:
            sim = query_thought.similarity(thought)
            similarities.append((thought, sim))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get thought space statistics"""
        return {
            'enabled': self.enabled,
            'total_thoughts': len(self.thought_history),
            'model': 'all-MiniLM-L6-v2' if self.enabled else None
        }


@dataclass
class ReasoningStep:
    """Single step in a reasoning chain"""
    step_number: int
    thought: str
    reasoning: str
    conclusion: Optional[str] = None
    confidence: float = 0.0
    thought_vector: Optional[ThoughtVector] = None


class ChainOfThought:
    """
    Multi-step reasoning with internal dialogue.
    The brain "thinks out loud" internally before responding.
    """
    
    def __init__(self, thought_space: ThoughtSpace, local_intelligence: Any = None):
        self.thought_space = thought_space
        self.local_intelligence = local_intelligence
        self.reasoning_chains: List[List[ReasoningStep]] = []
    
    async def reason(self, query: str, max_steps: int = 5) -> List[ReasoningStep]:
        """
        Perform multi-step reasoning on a query.
        
        Process:
        1. Break down the query
        2. Generate sub-questions
        3. Reason through each step
        4. Build towards conclusion
        """
        steps = []
        
        # Step 1: Understand the query
        step1 = await self._generate_step(
            step_number=1,
            prompt=f"First, let me understand: {query}\n\nWhat is being asked here?",
            previous_steps=[]
        )
        steps.append(step1)
        
        # Step 2: Break down the problem
        step2 = await self._generate_step(
            step_number=2,
            prompt=f"Given: {step1.conclusion}\n\nWhat are the key sub-problems or aspects to address?",
            previous_steps=steps
        )
        steps.append(step2)
        
        # Step 3-N: Reason through sub-problems
        for i in range(3, max_steps):
            step = await self._generate_step(
                step_number=i,
                prompt=f"Building on: {step2.conclusion}\n\nLet me reason through this step by step...",
                previous_steps=steps
            )
            steps.append(step)
            
            # Check if we reached a conclusion
            if self._is_conclusive(step):
                break
        
        # Final step: Synthesize conclusion
        final_step = await self._synthesize_conclusion(steps, query)
        steps.append(final_step)
        
        self.reasoning_chains.append(steps)
        return steps
    
    async def _generate_step(self, step_number: int, prompt: str, 
                            previous_steps: List[ReasoningStep]) -> ReasoningStep:
        """Generate a single reasoning step"""
        
        # Build context from previous steps
        context = "\n".join([
            f"Step {s.step_number}: {s.conclusion}" 
            for s in previous_steps if s.conclusion
        ])
        
        full_prompt = f"{context}\n\n{prompt}"
        
        # Get reasoning from model (prefer cloud for speed)
        if self.local_intelligence:
            try:
                result = await self.local_intelligence.think(
                    full_prompt,
                    task_type="reasoning",
                    prefer_local=False  # Use cloud for faster responses
                )
                reasoning = result.get('response', '')[:500]  # Limit length
            except Exception as e:
                reasoning = f"[Reasoning step {step_number}]"
        else:
            reasoning = f"[Reasoning step {step_number}]"
        
        # Extract conclusion (last sentence or summary)
        conclusion = self._extract_conclusion(reasoning)
        
        # Create thought vector
        thought_vector = self.thought_space.encode_thought(
            conclusion or reasoning,
            source="chain_of_thought"
        )
        
        return ReasoningStep(
            step_number=step_number,
            thought=prompt,
            reasoning=reasoning,
            conclusion=conclusion,
            confidence=0.8,
            thought_vector=thought_vector
        )
    
    def _extract_conclusion(self, text: str) -> str:
        """Extract conclusion from reasoning text"""
        # Simple heuristic: last sentence or first 200 chars
        sentences = text.split('.')
        if sentences:
            return sentences[-1].strip()
        return text[:200]
    
    def _is_conclusive(self, step: ReasoningStep) -> bool:
        """Check if step reaches a conclusion"""
        # Simple heuristic: check for conclusive words
        conclusive_words = ['therefore', 'thus', 'conclude', 'answer is', 'result is']
        return any(word in step.reasoning.lower() for word in conclusive_words)
    
    async def _synthesize_conclusion(self, steps: List[ReasoningStep], 
                                    original_query: str) -> ReasoningStep:
        """Synthesize final conclusion from all steps"""
        
        summary = "\n".join([
            f"{i+1}. {step.conclusion}" 
            for i, step in enumerate(steps) if step.conclusion
        ])
        
        prompt = f"Original question: {original_query}\n\nReasoning steps:\n{summary}\n\nFinal answer:"
        
        if self.local_intelligence:
            try:
                result = await self.local_intelligence.think(
                    prompt,
                    task_type="reasoning",
                    prefer_local=False  # Use cloud for faster responses
                )
                conclusion = result.get('response', '')
            except:
                conclusion = summary
        else:
            conclusion = summary
        
        return ReasoningStep(
            step_number=len(steps) + 1,
            thought="Final synthesis",
            reasoning=conclusion,
            conclusion=conclusion,
            confidence=0.9
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get chain-of-thought statistics"""
        total_chains = len(self.reasoning_chains)
        avg_steps = sum(len(chain) for chain in self.reasoning_chains) / total_chains if total_chains > 0 else 0
        
        return {
            'total_chains': total_chains,
            'avg_steps_per_chain': avg_steps
        }


class ConceptFormation:
    """
    Form abstract concepts from experiences.
    Learns patterns and creates higher-level abstractions.
    """
    
    def __init__(self, thought_space: ThoughtSpace):
        self.thought_space = thought_space
        self.concepts: Dict[str, List[ThoughtVector]] = {}
        self.concept_vectors: Dict[str, np.ndarray] = {}
    
    def learn_concept(self, concept_name: str, examples: List[str]):
        """Learn a concept from examples"""
        if not self.thought_space.enabled:
            return
        
        # Encode all examples as thought vectors
        thought_vectors = []
        for example in examples:
            thought = self.thought_space.encode_thought(example, source="concept_learning")
            if thought:
                thought_vectors.append(thought)
        
        if thought_vectors:
            self.concepts[concept_name] = thought_vectors
            
            # Create concept vector as centroid of examples
            vectors = np.array([t.vector for t in thought_vectors])
            centroid = np.mean(vectors, axis=0)
            self.concept_vectors[concept_name] = centroid
    
    def recognize_concept(self, text: str, threshold: float = 0.7) -> Optional[str]:
        """Recognize which concept this text belongs to"""
        if not self.thought_space.enabled:
            return None
        
        thought = self.thought_space.encode_thought(text, source="concept_recognition")
        if not thought:
            return None
        
        # Find most similar concept
        best_concept = None
        best_similarity = 0.0
        
        for concept_name, concept_vector in self.concept_vectors.items():
            similarity = float(np.dot(thought.vector, concept_vector) / 
                             (np.linalg.norm(thought.vector) * np.linalg.norm(concept_vector)))
            
            if similarity > best_similarity and similarity > threshold:
                best_similarity = similarity
                best_concept = concept_name
        
        return best_concept
    
    def abstract_from_examples(self, examples: List[str]) -> Optional[str]:
        """Create abstract concept from examples"""
        if not self.thought_space.enabled:
            return None
        
        # Find common patterns (simplified)
        # In a real system, this would use more sophisticated abstraction
        common_words = set()
        for example in examples:
            words = example.lower().split()
            if not common_words:
                common_words = set(words)
            else:
                common_words = common_words.intersection(set(words))
        
        if common_words:
            return f"Abstract concept: {', '.join(common_words)}"
        return "Complex abstract pattern"
    
    def get_stats(self) -> Dict[str, Any]:
        """Get concept formation statistics"""
        return {
            'total_concepts': len(self.concepts),
            'concepts': list(self.concepts.keys())
        }


class CreativeSynthesis:
    """
    Combine ideas in novel ways.
    The "creativity" component of the brain.
    """
    
    def __init__(self, thought_space: ThoughtSpace):
        self.thought_space = thought_space
        self.syntheses: List[Dict[str, Any]] = []
    
    async def synthesize(self, ideas: List[str], goal: str = "creative combination") -> str:
        """
        Combine multiple ideas into something new.
        
        Process:
        1. Convert ideas to thought vectors
        2. Find interesting combinations
        3. Generate novel synthesis
        """
        
        if not self.thought_space.enabled:
            # Fallback: simple text combination
            return f"Synthesis: {' + '.join(ideas)}"
        
        # Convert ideas to thoughts
        thought_vectors = []
        for idea in ideas:
            thought = self.thought_space.encode_thought(idea, source="creativity")
            if thought:
                thought_vectors.append(thought)
        
        if len(thought_vectors) < 2:
            return ideas[0] if ideas else "No synthesis possible"
        
        # Combine thought vectors
        combined = thought_vectors[0]
        for thought in thought_vectors[1:]:
            combined = combined.combine(thought, weight=0.5)
        
        # Generate creative synthesis
        synthesis = f"Creative synthesis of: {' + '.join(ideas)}\n"
        synthesis += f"Novel insight: {combined.content}"
        
        self.syntheses.append({
            'ideas': ideas,
            'goal': goal,
            'synthesis': synthesis,
            'timestamp': datetime.now().timestamp()
        })
        
        return synthesis
    
    def analogical_reasoning(self, source: str, target: str) -> str:
        """Create analogy between source and target domains"""
        if not self.thought_space.enabled:
            return f"{source} is like {target}"
        
        source_thought = self.thought_space.encode_thought(source)
        target_thought = self.thought_space.encode_thought(target)
        
        if source_thought and target_thought:
            similarity = source_thought.similarity(target_thought)
            return f"{source} is like {target} (similarity: {similarity:.2f})"
        
        return f"{source} is like {target}"
    
    def get_stats(self) -> Dict[str, Any]:
        """Get creative synthesis statistics"""
        return {
            'total_syntheses': len(self.syntheses),
            'recent_syntheses': self.syntheses[-5:] if self.syntheses else []
        }


class NeuralReasoningEngine:
    """
    Main orchestrator for neural reasoning.
    Combines all reasoning components into a unified system.
    """
    
    def __init__(self, local_intelligence: Any = None):
        self.thought_space = ThoughtSpace()
        self.chain_of_thought = ChainOfThought(self.thought_space, local_intelligence)
        self.concept_formation = ConceptFormation(self.thought_space)
        self.creative_synthesis = CreativeSynthesis(self.thought_space)
        
        self.reasoning_count = 0
    
    async def reason(self, query: str, mode: str = "chain_of_thought") -> Dict[str, Any]:
        """
        Main reasoning interface.
        
        Modes:
        - chain_of_thought: Multi-step reasoning
        - creative: Creative synthesis
        - conceptual: Concept-based reasoning
        """
        self.reasoning_count += 1
        
        if mode == "chain_of_thought":
            steps = await self.chain_of_thought.reason(query)
            return {
                'mode': 'chain_of_thought',
                'steps': len(steps),
                'reasoning': [
                    {
                        'step': s.step_number,
                        'thought': s.thought,
                        'conclusion': s.conclusion,
                        'confidence': s.confidence
                    }
                    for s in steps
                ],
                'final_answer': steps[-1].conclusion if steps else None
            }
        
        elif mode == "creative":
            # Extract ideas from query
            ideas = query.split(',')  # Simple split
            synthesis = await self.creative_synthesis.synthesize(ideas)
            return {
                'mode': 'creative',
                'synthesis': synthesis
            }
        
        elif mode == "conceptual":
            # Recognize concepts in query
            concept = self.concept_formation.recognize_concept(query)
            return {
                'mode': 'conceptual',
                'recognized_concept': concept,
                'query': query
            }
        
        return {'mode': mode, 'result': 'Unknown mode'}
    
    def learn_concept(self, concept_name: str, examples: List[str]):
        """Teach the brain a new concept"""
        self.concept_formation.learn_concept(concept_name, examples)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive reasoning statistics"""
        return {
            'reasoning_count': self.reasoning_count,
            'thought_space': self.thought_space.get_stats(),
            'chain_of_thought': self.chain_of_thought.get_stats(),
            'concept_formation': self.concept_formation.get_stats(),
            'creative_synthesis': self.creative_synthesis.get_stats()
        }


# Convenience function
def create_neural_reasoning(local_intelligence: Any = None) -> NeuralReasoningEngine:
    """Create neural reasoning engine"""
    return NeuralReasoningEngine(local_intelligence)
