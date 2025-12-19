#!/usr/bin/env python3
"""
Advanced Reasoning System
=========================

Implements multiple reasoning strategies:
- Chain-of-Thought (CoT)
- Tree-of-Thought (ToT)
- Self-Reflection
- ReAct (Reasoning + Acting)
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass
import json
import re

logger = logging.getLogger(__name__)


class ReasoningStrategy(Enum):
    """Available reasoning strategies"""
    DIRECT = "direct"
    CHAIN_OF_THOUGHT = "chain_of_thought"
    TREE_OF_THOUGHT = "tree_of_thought"
    SELF_REFLECTION = "self_reflection"
    REACT = "react"


@dataclass
class ReasoningStep:
    """Single step in reasoning process"""
    step_number: int
    thought: str
    action: Optional[str] = None
    observation: Optional[str] = None
    confidence: float = 1.0


@dataclass
class ReasoningResult:
    """Result of reasoning process"""
    strategy: str
    steps: List[ReasoningStep]
    final_answer: str
    total_confidence: float
    metadata: Dict[str, Any]


class ChainOfThoughtReasoner:
    """
    Chain-of-Thought Reasoning
    Breaks down complex problems into sequential steps
    """
    
    def __init__(self):
        self.max_steps = 10
        
    def create_cot_prompt(self, query: str, context: Optional[str] = None) -> str:
        """Create a chain-of-thought prompt"""
        prompt = f"""Let's approach this step by step:

Question: {query}
"""
        if context:
            prompt += f"\nContext: {context}\n"
            
        prompt += """
Please think through this carefully, breaking down your reasoning into clear steps:

Step 1: [Understand the problem]
Step 2: [Identify key information]
Step 3: [Apply relevant knowledge]
Step 4: [Reason through the solution]
Step 5: [Verify the answer]

Final Answer: [Your conclusion]
"""
        return prompt
    
    def parse_cot_response(self, response: str) -> List[ReasoningStep]:
        """Parse response into reasoning steps"""
        steps = []
        
        # Extract steps using regex
        step_pattern = r'Step (\d+):\s*(.+?)(?=Step \d+:|Final Answer:|$)'
        matches = re.finditer(step_pattern, response, re.DOTALL)
        
        for match in matches:
            step_num = int(match.group(1))
            thought = match.group(2).strip()
            steps.append(ReasoningStep(
                step_number=step_num,
                thought=thought,
                confidence=1.0
            ))
        
        return steps
    
    def reason(self, query: str, llm_function, context: Optional[str] = None) -> ReasoningResult:
        """
        Execute chain-of-thought reasoning
        
        Args:
            query: Question to reason about
            llm_function: Function to call LLM (takes prompt, returns response)
            context: Optional context
            
        Returns:
            ReasoningResult with steps and answer
        """
        # Create CoT prompt
        prompt = self.create_cot_prompt(query, context)
        
        # Get LLM response
        response = llm_function(prompt)
        
        # Parse steps
        steps = self.parse_cot_response(response)
        
        # Extract final answer
        final_answer_match = re.search(r'Final Answer:\s*(.+?)$', response, re.DOTALL)
        final_answer = final_answer_match.group(1).strip() if final_answer_match else response
        
        return ReasoningResult(
            strategy=ReasoningStrategy.CHAIN_OF_THOUGHT.value,
            steps=steps,
            final_answer=final_answer,
            total_confidence=sum(s.confidence for s in steps) / len(steps) if steps else 1.0,
            metadata={"prompt_tokens": len(prompt.split()), "response_tokens": len(response.split())}
        )


class TreeOfThoughtReasoner:
    """
    Tree-of-Thought Reasoning
    Explores multiple reasoning paths and selects the best
    """
    
    def __init__(self, branching_factor: int = 3, max_depth: int = 3):
        self.branching_factor = branching_factor
        self.max_depth = max_depth
        
    def generate_thoughts(self, query: str, current_path: List[str], llm_function) -> List[str]:
        """Generate multiple possible next thoughts"""
        prompt = f"""Given this problem: {query}

Current reasoning path:
{chr(10).join(f"{i+1}. {thought}" for i, thought in enumerate(current_path))}

Generate {self.branching_factor} different next steps to continue reasoning:
1. [First alternative approach]
2. [Second alternative approach]
3. [Third alternative approach]
"""
        response = llm_function(prompt)
        
        # Parse alternatives
        thoughts = []
        for line in response.split('\n'):
            if re.match(r'^\d+\.', line):
                thought = re.sub(r'^\d+\.\s*', '', line).strip()
                if thought:
                    thoughts.append(thought)
        
        return thoughts[:self.branching_factor]
    
    def evaluate_path(self, query: str, path: List[str], llm_function) -> float:
        """Evaluate how promising a reasoning path is"""
        prompt = f"""Question: {query}

Reasoning path so far:
{chr(10).join(f"{i+1}. {thought}" for i, thought in enumerate(path))}

On a scale of 0.0 to 1.0, how likely is this reasoning path to lead to the correct answer?
Rate only with a number (e.g., 0.85):"""
        
        response = llm_function(prompt)
        
        # Extract score
        try:
            score = float(re.search(r'(\d+\.?\d*)', response).group(1))
            return min(max(score, 0.0), 1.0)
        except:
            return 0.5  # Default medium confidence
    
    def reason(self, query: str, llm_function, context: Optional[str] = None) -> ReasoningResult:
        """
        Execute tree-of-thought reasoning
        
        Args:
            query: Question to reason about
            llm_function: Function to call LLM
            context: Optional context
            
        Returns:
            ReasoningResult with best path
        """
        # Start with empty path
        paths = [[]]
        path_scores = [1.0]
        
        # Explore tree
        for depth in range(self.max_depth):
            new_paths = []
            new_scores = []
            
            # Expand each path
            for path, score in zip(paths, path_scores):
                thoughts = self.generate_thoughts(query, path, llm_function)
                
                for thought in thoughts:
                    new_path = path + [thought]
                    new_score = self.evaluate_path(query, new_path, llm_function)
                    new_paths.append(new_path)
                    new_scores.append(new_score)
            
            # Keep only top paths (beam search)
            if new_paths:
                sorted_indices = sorted(range(len(new_scores)), key=lambda i: new_scores[i], reverse=True)
                top_k = min(self.branching_factor, len(sorted_indices))
                paths = [new_paths[i] for i in sorted_indices[:top_k]]
                path_scores = [new_scores[i] for i in sorted_indices[:top_k]]
        
        # Select best path
        best_idx = path_scores.index(max(path_scores))
        best_path = paths[best_idx]
        best_score = path_scores[best_idx]
        
        # Convert to steps
        steps = [
            ReasoningStep(step_number=i+1, thought=thought, confidence=best_score)
            for i, thought in enumerate(best_path)
        ]
        
        # Generate final answer from best path
        final_prompt = f"""Question: {query}

Best reasoning path:
{chr(10).join(f"{i+1}. {thought}" for i, thought in enumerate(best_path))}

Based on this reasoning, provide the final answer:"""
        
        final_answer = llm_function(final_prompt)
        
        return ReasoningResult(
            strategy=ReasoningStrategy.TREE_OF_THOUGHT.value,
            steps=steps,
            final_answer=final_answer,
            total_confidence=best_score,
            metadata={
                "paths_explored": len(paths),
                "branching_factor": self.branching_factor,
                "max_depth": self.max_depth
            }
        )


class SelfReflectionReasoner:
    """
    Self-Reflection Reasoning
    Generates answer, critiques it, then refines
    """
    
    def __init__(self, max_iterations: int = 3):
        self.max_iterations = max_iterations
        
    def generate_initial_answer(self, query: str, llm_function, context: Optional[str] = None) -> str:
        """Generate initial answer attempt"""
        prompt = f"Question: {query}\n"
        if context:
            prompt += f"Context: {context}\n"
        prompt += "\nProvide your answer:"
        
        return llm_function(prompt)
    
    def critique_answer(self, query: str, answer: str, llm_function) -> Tuple[str, float]:
        """Critique the answer and identify issues"""
        prompt = f"""Question: {query}
Answer: {answer}

Critique this answer:
1. Is it accurate?
2. Is it complete?
3. Are there any logical flaws?
4. What could be improved?

Provide critique and a quality score (0.0-1.0):"""
        
        response = llm_function(prompt)
        
        # Extract score
        try:
            score = float(re.search(r'score:?\s*(\d+\.?\d*)', response, re.IGNORECASE).group(1))
            score = min(max(score, 0.0), 1.0)
        except:
            score = 0.7  # Default
        
        return response, score
    
    def refine_answer(self, query: str, previous_answer: str, critique: str, llm_function) -> str:
        """Refine answer based on critique"""
        prompt = f"""Question: {query}

Previous answer: {previous_answer}

Critique: {critique}

Provide an improved answer addressing the critique:"""
        
        return llm_function(prompt)
    
    def reason(self, query: str, llm_function, context: Optional[str] = None) -> ReasoningResult:
        """
        Execute self-reflection reasoning
        
        Args:
            query: Question to reason about
            llm_function: Function to call LLM
            context: Optional context
            
        Returns:
            ReasoningResult with refined answer
        """
        steps = []
        
        # Initial answer
        answer = self.generate_initial_answer(query, llm_function, context)
        steps.append(ReasoningStep(
            step_number=1,
            thought="Initial answer generation",
            observation=answer
        ))
        
        # Iterative refinement
        for iteration in range(self.max_iterations):
            # Critique
            critique, score = self.critique_answer(query, answer, llm_function)
            steps.append(ReasoningStep(
                step_number=len(steps) + 1,
                thought=f"Critique iteration {iteration + 1}",
                observation=critique,
                confidence=score
            ))
            
            # If good enough, stop
            if score >= 0.9:
                break
            
            # Refine
            answer = self.refine_answer(query, answer, critique, llm_function)
            steps.append(ReasoningStep(
                step_number=len(steps) + 1,
                thought=f"Refinement iteration {iteration + 1}",
                observation=answer,
                confidence=score
            ))
        
        return ReasoningResult(
            strategy=ReasoningStrategy.SELF_REFLECTION.value,
            steps=steps,
            final_answer=answer,
            total_confidence=steps[-1].confidence if steps else 1.0,
            metadata={"iterations": len(steps) // 2}
        )


class ReActReasoner:
    """
    ReAct: Reasoning + Acting
    Interleaves thinking with actions (tool usage)
    """
    
    def __init__(self, available_tools: Optional[List[str]] = None):
        self.available_tools = available_tools or []
        self.max_steps = 10
        
    def create_react_prompt(self, query: str, tools: List[str]) -> str:
        """Create ReAct prompt"""
        tools_str = "\n".join(f"- {tool}" for tool in tools)
        
        return f"""You have access to these tools:
{tools_str}

Question: {query}

Think step-by-step using this format:
Thought: [Your reasoning]
Action: [Tool to use or "Answer" if ready]
Observation: [Result of action]

Repeat until you can provide the final answer.

Let's begin:
Thought:"""
    
    def parse_react_step(self, response: str) -> Tuple[str, str, str]:
        """Parse a ReAct step"""
        thought = re.search(r'Thought:\s*(.+?)(?=Action:|$)', response, re.DOTALL)
        action = re.search(r'Action:\s*(.+?)(?=Observation:|$)', response, re.DOTALL)
        observation = re.search(r'Observation:\s*(.+?)(?=Thought:|$)', response, re.DOTALL)
        
        return (
            thought.group(1).strip() if thought else "",
            action.group(1).strip() if action else "",
            observation.group(1).strip() if observation else ""
        )
    
    def reason(
        self,
        query: str,
        llm_function,
        tool_executor=None,
        context: Optional[str] = None
    ) -> ReasoningResult:
        """
        Execute ReAct reasoning
        
        Args:
            query: Question to reason about
            llm_function: Function to call LLM
            tool_executor: Function to execute tools
            context: Optional context
            
        Returns:
            ReasoningResult with reasoning and actions
        """
        steps = []
        conversation_history = self.create_react_prompt(query, self.available_tools)
        
        for step_num in range(self.max_steps):
            # Get LLM response
            response = llm_function(conversation_history)
            
            # Parse step
            thought, action, observation = self.parse_react_step(response)
            
            # Execute action if tool executor available
            if action and action.lower() != "answer" and tool_executor:
                observation = tool_executor(action)
            
            # Record step
            steps.append(ReasoningStep(
                step_number=step_num + 1,
                thought=thought,
                action=action,
                observation=observation
            ))
            
            # Update conversation history
            conversation_history += f"\n\nThought: {thought}\nAction: {action}\nObservation: {observation}"
            
            # Check if done
            if action.lower() == "answer" or "final answer" in response.lower():
                break
        
        # Extract final answer
        final_answer = steps[-1].observation if steps else "Unable to determine answer"
        
        return ReasoningResult(
            strategy=ReasoningStrategy.REACT.value,
            steps=steps,
            final_answer=final_answer,
            total_confidence=0.8,  # Default confidence for ReAct
            metadata={"steps_taken": len(steps), "tools_used": len([s for s in steps if s.action])}
        )


class AdvancedReasoningSystem:
    """
    Unified Advanced Reasoning System
    Orchestrates all reasoning strategies
    """
    
    def __init__(self):
        self.cot = ChainOfThoughtReasoner()
        self.tot = TreeOfThoughtReasoner()
        self.reflection = SelfReflectionReasoner()
        self.react = ReActReasoner()
        
        self.enabled = True
        logger.info("✅ Advanced Reasoning System initialized")
    
    def reason(
        self,
        query: str,
        strategy: ReasoningStrategy,
        llm_function,
        tool_executor=None,
        context: Optional[str] = None
    ) -> ReasoningResult:
        """
        Execute reasoning with specified strategy
        
        Args:
            query: Question to reason about
            strategy: Reasoning strategy to use
            llm_function: Function to call LLM
            tool_executor: Optional tool executor for ReAct
            context: Optional context
            
        Returns:
            ReasoningResult with steps and answer
        """
        if not self.enabled:
            # Fallback to direct
            response = llm_function(query)
            return ReasoningResult(
                strategy=ReasoningStrategy.DIRECT.value,
                steps=[ReasoningStep(1, "Direct response", confidence=1.0)],
                final_answer=response,
                total_confidence=1.0,
                metadata={}
            )
        
        try:
            if strategy == ReasoningStrategy.CHAIN_OF_THOUGHT:
                return self.cot.reason(query, llm_function, context)
            
            elif strategy == ReasoningStrategy.TREE_OF_THOUGHT:
                return self.tot.reason(query, llm_function, context)
            
            elif strategy == ReasoningStrategy.SELF_REFLECTION:
                return self.reflection.reason(query, llm_function, context)
            
            elif strategy == ReasoningStrategy.REACT:
                return self.react.reason(query, llm_function, tool_executor, context)
            
            else:  # DIRECT
                response = llm_function(query)
                return ReasoningResult(
                    strategy=ReasoningStrategy.DIRECT.value,
                    steps=[],
                    final_answer=response,
                    total_confidence=1.0,
                    metadata={}
                )
        
        except Exception as e:
            logger.error(f"❌ Reasoning failed: {e}")
            # Fallback to direct
            response = llm_function(query)
            return ReasoningResult(
                strategy="direct_fallback",
                steps=[],
                final_answer=response,
                total_confidence=0.5,
                metadata={"error": str(e)}
            )
    
    def auto_select_strategy(self, query: str, complexity_score: Optional[float] = None) -> ReasoningStrategy:
        """
        Automatically select best reasoning strategy based on query
        
        Args:
            query: The question
            complexity_score: Optional pre-computed complexity (0-1)
            
        Returns:
            Best strategy for this query
        """
        # Simple heuristics (can be made smarter with ML)
        query_lower = query.lower()
        
        # Check for multi-step reasoning needs
        if any(word in query_lower for word in ['step', 'how', 'why', 'explain', 'process']):
            return ReasoningStrategy.CHAIN_OF_THOUGHT
        
        # Check for planning/exploration needs
        if any(word in query_lower for word in ['plan', 'strategy', 'approach', 'multiple ways']):
            return ReasoningStrategy.TREE_OF_THOUGHT
        
        # Check for tool usage needs
        if any(word in query_lower for word in ['calculate', 'search', 'find', 'look up']):
            return ReasoningStrategy.REACT
        
        # Check for verification needs
        if any(word in query_lower for word in ['verify', 'check', 'correct', 'validate']):
            return ReasoningStrategy.SELF_REFLECTION
        
        # Default to chain-of-thought for complex queries
        if len(query.split()) > 20 or complexity_score and complexity_score > 0.7:
            return ReasoningStrategy.CHAIN_OF_THOUGHT
        
        # Simple queries use direct
        return ReasoningStrategy.DIRECT


# Convenience function
def create_reasoning_system() -> AdvancedReasoningSystem:
    """Create and return reasoning system"""
    return AdvancedReasoningSystem()
