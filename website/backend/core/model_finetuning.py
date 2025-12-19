#!/usr/bin/env python3
"""
Model Fine-tuning System
========================

Enables model adaptation and fine-tuning:
- Training data preparation
- LoRA/QLoRA fine-tuning support
- Model evaluation and metrics
- A/B testing framework
- Performance tracking
"""

import logging
import json
import time
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import statistics
import hashlib

logger = logging.getLogger(__name__)


class FinetuningMethod(Enum):
    """Fine-tuning methods"""
    FULL = "full"                  # Full model fine-tuning
    LORA = "lora"                  # Low-Rank Adaptation
    QLORA = "qlora"                # Quantized LoRA
    PREFIX_TUNING = "prefix_tuning"
    PROMPT_TUNING = "prompt_tuning"
    ADAPTER = "adapter"


class DatasetType(Enum):
    """Training dataset types"""
    INSTRUCTION = "instruction"    # Instruction-response pairs
    CONVERSATION = "conversation"  # Multi-turn conversations
    COMPLETION = "completion"      # Text completion
    CLASSIFICATION = "classification"
    QA = "qa"                     # Question-answering


@dataclass
class TrainingExample:
    """Single training example"""
    id: str
    input_text: str
    output_text: str
    metadata: Dict[str, Any]
    quality_score: float  # 0.0 to 1.0
    created_at: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "input": self.input_text,
            "output": self.output_text,
            "metadata": self.metadata,
            "quality_score": self.quality_score,
            "created_at": self.created_at
        }
    
    def to_training_format(self, format_type: str = "openai") -> Dict[str, Any]:
        """Convert to specific training format"""
        if format_type == "openai":
            return {
                "messages": [
                    {"role": "user", "content": self.input_text},
                    {"role": "assistant", "content": self.output_text}
                ]
            }
        elif format_type == "alpaca":
            return {
                "instruction": self.input_text,
                "output": self.output_text
            }
        else:
            return self.to_dict()


@dataclass
class FineTuneConfig:
    """Fine-tuning configuration"""
    method: FinetuningMethod
    base_model: str
    dataset_type: DatasetType
    num_epochs: int = 3
    batch_size: int = 4
    learning_rate: float = 1e-4
    warmup_steps: int = 100
    lora_rank: int = 8  # For LoRA/QLoRA
    lora_alpha: int = 16
    lora_dropout: float = 0.1
    target_modules: List[str] = field(default_factory=lambda: ["q_proj", "v_proj"])
    max_seq_length: int = 2048
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method.value,
            "base_model": self.base_model,
            "dataset_type": self.dataset_type.value,
            "num_epochs": self.num_epochs,
            "batch_size": self.batch_size,
            "learning_rate": self.learning_rate,
            "warmup_steps": self.warmup_steps,
            "lora_rank": self.lora_rank,
            "lora_alpha": self.lora_alpha,
            "lora_dropout": self.lora_dropout,
            "target_modules": self.target_modules,
            "max_seq_length": self.max_seq_length,
            "metadata": self.metadata
        }


@dataclass
class EvaluationMetrics:
    """Model evaluation metrics"""
    accuracy: Optional[float] = None
    perplexity: Optional[float] = None
    bleu_score: Optional[float] = None
    rouge_scores: Dict[str, float] = field(default_factory=dict)
    f1_score: Optional[float] = None
    latency_ms: Optional[float] = None
    throughput: Optional[float] = None
    custom_metrics: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "accuracy": self.accuracy,
            "perplexity": self.perplexity,
            "bleu_score": self.bleu_score,
            "rouge_scores": self.rouge_scores,
            "f1_score": self.f1_score,
            "latency_ms": self.latency_ms,
            "throughput": self.throughput,
            "custom_metrics": self.custom_metrics
        }


class TrainingDataPreparator:
    """Prepare training data from interactions"""
    
    def __init__(self):
        self.examples: Dict[str, TrainingExample] = {}
        self.example_counter = 0
        
    def add_example(
        self,
        input_text: str,
        output_text: str,
        quality_score: float = 0.8,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TrainingExample:
        """
        Add training example
        
        Args:
            input_text: Input/prompt text
            output_text: Expected output
            quality_score: Quality score (0.0-1.0)
            metadata: Additional metadata
            
        Returns:
            Created TrainingExample
        """
        self.example_counter += 1
        example_id = self._generate_id(input_text, output_text)
        
        example = TrainingExample(
            id=example_id,
            input_text=input_text,
            output_text=output_text,
            metadata=metadata or {},
            quality_score=quality_score,
            created_at=time.time()
        )
        
        self.examples[example_id] = example
        return example
    
    def add_from_conversation(
        self,
        conversation: List[Tuple[str, str]],  # (role, content)
        quality_score: float = 0.8
    ):
        """Add examples from conversation history"""
        for i in range(0, len(conversation) - 1, 2):
            if i + 1 < len(conversation):
                user_msg = conversation[i]
                assistant_msg = conversation[i + 1]
                
                if user_msg[0] == "user" and assistant_msg[0] == "assistant":
                    self.add_example(
                        input_text=user_msg[1],
                        output_text=assistant_msg[1],
                        quality_score=quality_score,
                        metadata={"source": "conversation"}
                    )
    
    def filter_by_quality(self, min_score: float = 0.7) -> List[TrainingExample]:
        """Filter examples by quality score"""
        filtered = [
            ex for ex in self.examples.values()
            if ex.quality_score >= min_score
        ]
        filtered.sort(key=lambda ex: ex.quality_score, reverse=True)
        return filtered
    
    def export_dataset(
        self,
        format_type: str = "openai",
        min_quality: float = 0.7,
        max_examples: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Export dataset in specific format
        
        Args:
            format_type: Export format
            min_quality: Minimum quality score
            max_examples: Maximum examples to export
            
        Returns:
            List of formatted examples
        """
        examples = self.filter_by_quality(min_quality)
        
        if max_examples:
            examples = examples[:max_examples]
        
        return [ex.to_training_format(format_type) for ex in examples]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get dataset statistics"""
        if not self.examples:
            return {"total": 0}
        
        scores = [ex.quality_score for ex in self.examples.values()]
        input_lengths = [len(ex.input_text) for ex in self.examples.values()]
        output_lengths = [len(ex.output_text) for ex in self.examples.values()]
        
        return {
            "total_examples": len(self.examples),
            "avg_quality_score": statistics.mean(scores),
            "avg_input_length": statistics.mean(input_lengths),
            "avg_output_length": statistics.mean(output_lengths),
            "high_quality_count": len(self.filter_by_quality(0.8))
        }
    
    def _generate_id(self, input_text: str, output_text: str) -> str:
        """Generate unique example ID"""
        combined = f"{input_text}:{output_text}:{time.time()}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]


class FineTuningJob:
    """Represents a fine-tuning job"""
    
    def __init__(
        self,
        job_id: str,
        config: FineTuneConfig,
        dataset_size: int
    ):
        self.job_id = job_id
        self.config = config
        self.dataset_size = dataset_size
        self.status = "pending"  # pending, running, completed, failed
        self.progress = 0.0  # 0.0 to 1.0
        self.current_epoch = 0
        self.loss_history: List[float] = []
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None
        self.error_message: Optional[str] = None
        self.checkpoints: List[str] = []
        
    def start(self):
        """Mark job as started"""
        self.status = "running"
        self.started_at = time.time()
        logger.info(f"Fine-tuning job started: {self.job_id}")
    
    def update_progress(self, epoch: int, loss: float, progress: float):
        """Update training progress"""
        self.current_epoch = epoch
        self.loss_history.append(loss)
        self.progress = progress
        
    def complete(self, checkpoint_path: str):
        """Mark job as completed"""
        self.status = "completed"
        self.completed_at = time.time()
        self.checkpoints.append(checkpoint_path)
        logger.info(f"Fine-tuning job completed: {self.job_id}")
    
    def fail(self, error: str):
        """Mark job as failed"""
        self.status = "failed"
        self.error_message = error
        self.completed_at = time.time()
        logger.error(f"Fine-tuning job failed: {self.job_id} - {error}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "job_id": self.job_id,
            "config": self.config.to_dict(),
            "dataset_size": self.dataset_size,
            "status": self.status,
            "progress": self.progress,
            "current_epoch": self.current_epoch,
            "loss_history": self.loss_history,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
            "checkpoints": self.checkpoints
        }


class ModelEvaluator:
    """Evaluate fine-tuned models"""
    
    def __init__(self):
        self.evaluation_history: List[Dict[str, Any]] = []
    
    def evaluate(
        self,
        model_id: str,
        test_data: List[TrainingExample],
        llm_function: Callable
    ) -> EvaluationMetrics:
        """
        Evaluate model on test data
        
        Args:
            model_id: Model identifier
            test_data: Test examples
            llm_function: Function to call model
            
        Returns:
            EvaluationMetrics
        """
        logger.info(f"Evaluating model: {model_id} on {len(test_data)} examples")
        
        correct = 0
        total_latency = 0.0
        
        for example in test_data:
            start_time = time.time()
            
            # Get model prediction
            try:
                prediction = llm_function(example.input_text)
                latency = (time.time() - start_time) * 1000  # ms
                total_latency += latency
                
                # Simple accuracy check (exact match or contains)
                if prediction.strip() == example.output_text.strip():
                    correct += 1
                elif example.output_text.strip().lower() in prediction.lower():
                    correct += 0.5  # Partial credit
                    
            except Exception as e:
                logger.error(f"Evaluation error: {e}")
        
        accuracy = correct / len(test_data) if test_data else 0
        avg_latency = total_latency / len(test_data) if test_data else 0
        
        metrics = EvaluationMetrics(
            accuracy=accuracy,
            latency_ms=avg_latency,
            throughput=1000 / avg_latency if avg_latency > 0 else 0
        )
        
        # Store evaluation
        self.evaluation_history.append({
            "model_id": model_id,
            "timestamp": time.time(),
            "metrics": metrics.to_dict(),
            "test_size": len(test_data)
        })
        
        return metrics
    
    def compare_models(
        self,
        model_a_id: str,
        model_b_id: str
    ) -> Dict[str, Any]:
        """Compare two models"""
        eval_a = next((e for e in reversed(self.evaluation_history) if e["model_id"] == model_a_id), None)
        eval_b = next((e for e in reversed(self.evaluation_history) if e["model_id"] == model_b_id), None)
        
        if not eval_a or not eval_b:
            return {"error": "Model evaluations not found"}
        
        metrics_a = eval_a["metrics"]
        metrics_b = eval_b["metrics"]
        
        comparison = {
            "model_a": model_a_id,
            "model_b": model_b_id,
            "accuracy_diff": metrics_a.get("accuracy", 0) - metrics_b.get("accuracy", 0),
            "latency_diff_ms": metrics_a.get("latency_ms", 0) - metrics_b.get("latency_ms", 0),
            "better_model": None
        }
        
        # Determine better model (accuracy weighted more)
        score_a = metrics_a.get("accuracy", 0) * 2 - (metrics_a.get("latency_ms", 0) / 1000)
        score_b = metrics_b.get("accuracy", 0) * 2 - (metrics_b.get("latency_ms", 0) / 1000)
        
        comparison["better_model"] = model_a_id if score_a > score_b else model_b_id
        
        return comparison


class ABTestFramework:
    """A/B testing for model variants"""
    
    def __init__(self):
        self.experiments: Dict[str, Dict[str, Any]] = {}
        self.experiment_counter = 0
        
    def create_experiment(
        self,
        name: str,
        model_a_id: str,
        model_b_id: str,
        traffic_split: float = 0.5  # Percentage to model A
    ) -> str:
        """
        Create A/B test experiment
        
        Args:
            name: Experiment name
            model_a_id: First model ID
            model_b_id: Second model ID
            traffic_split: Traffic to model A (0.0-1.0)
            
        Returns:
            Experiment ID
        """
        self.experiment_counter += 1
        exp_id = f"exp_{self.experiment_counter}_{int(time.time())}"
        
        self.experiments[exp_id] = {
            "id": exp_id,
            "name": name,
            "model_a": model_a_id,
            "model_b": model_b_id,
            "traffic_split": traffic_split,
            "created_at": time.time(),
            "status": "active",
            "results": {
                "model_a": {"requests": 0, "avg_score": 0.0, "scores": []},
                "model_b": {"requests": 0, "avg_score": 0.0, "scores": []}
            }
        }
        
        logger.info(f"A/B experiment created: {name}")
        return exp_id
    
    def route_request(self, experiment_id: str) -> str:
        """
        Route request to model variant
        
        Args:
            experiment_id: Experiment ID
            
        Returns:
            Model ID to use
        """
        exp = self.experiments.get(experiment_id)
        if not exp:
            raise ValueError(f"Experiment not found: {experiment_id}")
        
        import random
        if random.random() < exp["traffic_split"]:
            return exp["model_a"]
        else:
            return exp["model_b"]
    
    def record_result(
        self,
        experiment_id: str,
        model_id: str,
        score: float
    ):
        """Record experiment result"""
        exp = self.experiments.get(experiment_id)
        if not exp:
            return
        
        variant = "model_a" if model_id == exp["model_a"] else "model_b"
        results = exp["results"][variant]
        
        results["requests"] += 1
        results["scores"].append(score)
        results["avg_score"] = statistics.mean(results["scores"])
    
    def get_experiment_results(self, experiment_id: str) -> Dict[str, Any]:
        """Get experiment results"""
        exp = self.experiments.get(experiment_id)
        if not exp:
            return {"error": "Experiment not found"}
        
        results_a = exp["results"]["model_a"]
        results_b = exp["results"]["model_b"]
        
        # Determine statistical significance (simplified)
        if results_a["requests"] < 30 or results_b["requests"] < 30:
            significance = "insufficient_data"
        else:
            score_diff = abs(results_a["avg_score"] - results_b["avg_score"])
            significance = "significant" if score_diff > 0.05 else "not_significant"
        
        return {
            "experiment_id": experiment_id,
            "name": exp["name"],
            "model_a": {
                "id": exp["model_a"],
                "requests": results_a["requests"],
                "avg_score": results_a["avg_score"]
            },
            "model_b": {
                "id": exp["model_b"],
                "requests": results_b["requests"],
                "avg_score": results_b["avg_score"]
            },
            "winner": exp["model_a"] if results_a["avg_score"] > results_b["avg_score"] else exp["model_b"],
            "significance": significance
        }


class ModelFinetuningSystem:
    """
    Unified Model Fine-tuning System
    Handles training, evaluation, and deployment
    """
    
    def __init__(self):
        self.data_preparator = TrainingDataPreparator()
        self.evaluator = ModelEvaluator()
        self.ab_framework = ABTestFramework()
        self.jobs: Dict[str, FineTuningJob] = {}
        self.job_counter = 0
        
        self.enabled = True
        logger.info("✅ Model Fine-tuning System initialized")
    
    def prepare_training_data(
        self,
        interactions: List[Tuple[str, str]],  # (input, output)
        quality_scores: Optional[List[float]] = None
    ) -> int:
        """
        Prepare training data from interactions
        
        Args:
            interactions: List of (input, output) tuples
            quality_scores: Optional quality scores
            
        Returns:
            Number of examples added
        """
        if quality_scores is None:
            quality_scores = [0.8] * len(interactions)
        
        for i, (input_text, output_text) in enumerate(interactions):
            self.data_preparator.add_example(
                input_text=input_text,
                output_text=output_text,
                quality_score=quality_scores[i] if i < len(quality_scores) else 0.8
            )
        
        logger.info(f"Added {len(interactions)} training examples")
        return len(interactions)
    
    def create_finetuning_job(
        self,
        config: FineTuneConfig,
        min_quality: float = 0.7
    ) -> str:
        """
        Create fine-tuning job
        
        Args:
            config: Fine-tuning configuration
            min_quality: Minimum quality for training data
            
        Returns:
            Job ID
        """
        # Get high-quality training data
        examples = self.data_preparator.filter_by_quality(min_quality)
        
        if len(examples) < 10:
            raise ValueError(f"Insufficient training data: {len(examples)} examples (minimum 10)")
        
        self.job_counter += 1
        job_id = f"ft_job_{self.job_counter}_{int(time.time())}"
        
        job = FineTuningJob(
            job_id=job_id,
            config=config,
            dataset_size=len(examples)
        )
        
        self.jobs[job_id] = job
        logger.info(f"Created fine-tuning job: {job_id} with {len(examples)} examples")
        
        return job_id
    
    def simulate_training(self, job_id: str):
        """
        Simulate training process (placeholder for actual training)
        In production, this would integrate with actual fine-tuning frameworks
        """
        job = self.jobs.get(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")
        
        job.start()
        
        # Simulate training epochs
        for epoch in range(job.config.num_epochs):
            # Simulate loss decrease
            loss = 2.0 / (epoch + 1)
            progress = (epoch + 1) / job.config.num_epochs
            job.update_progress(epoch + 1, loss, progress)
        
        # Complete job
        checkpoint = f"checkpoint_{job_id}_final"
        job.complete(checkpoint)
    
    def evaluate_model(
        self,
        model_id: str,
        test_interactions: List[Tuple[str, str]],
        llm_function: Callable
    ) -> EvaluationMetrics:
        """
        Evaluate fine-tuned model
        
        Args:
            model_id: Model identifier
            test_interactions: Test data
            llm_function: Model function
            
        Returns:
            EvaluationMetrics
        """
        # Convert to training examples
        test_data = [
            TrainingExample(
                id=f"test_{i}",
                input_text=inp,
                output_text=out,
                metadata={},
                quality_score=1.0,
                created_at=time.time()
            )
            for i, (inp, out) in enumerate(test_interactions)
        ]
        
        return self.evaluator.evaluate(model_id, test_data, llm_function)
    
    def compare_models(self, model_a_id: str, model_b_id: str) -> Dict[str, Any]:
        """Compare two models"""
        return self.evaluator.compare_models(model_a_id, model_b_id)
    
    def create_ab_test(
        self,
        name: str,
        model_a_id: str,
        model_b_id: str,
        traffic_split: float = 0.5
    ) -> str:
        """Create A/B test"""
        return self.ab_framework.create_experiment(
            name, model_a_id, model_b_id, traffic_split
        )
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get fine-tuning job status"""
        job = self.jobs.get(job_id)
        if not job:
            return {"error": "Job not found"}
        return job.to_dict()
    
    def get_dataset_stats(self) -> Dict[str, Any]:
        """Get training dataset statistics"""
        return self.data_preparator.get_statistics()


# Convenience function
def create_finetuning_system() -> ModelFinetuningSystem:
    """Create model fine-tuning system"""
    return ModelFinetuningSystem()
