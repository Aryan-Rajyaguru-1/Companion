#!/usr/bin/env python3
"""
Thread Manager - Centralized Thread Management System
======================================================

Manages all threads for CompanionBrain modules with autonomous decision-making.
The brain can manage threads, prioritize workloads, and optimize resource usage.

Architecture:
    All modules → ThreadManager → CompanionBrain (autonomous decision system)
    
Thread Categories:
    - Core Threads: Model routing, context management
    - Phase Threads: Knowledge retrieval, search, web intelligence, code execution
    - Advanced Threads: Reasoning, learning, optimization
    - AGI Threads: Personality, neural reasoning, self-learning, autonomy
    - Monitoring Threads: Performance, health checks, metrics
"""

import threading
import queue
import logging
import time
from typing import Dict, List, Optional, Any, Callable, Set
from datetime import datetime, timedelta
from enum import Enum
import uuid
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


class ThreadPriority(Enum):
    """Thread priority levels for autonomous decision-making"""
    CRITICAL = 1    # User-facing, must respond immediately
    HIGH = 2        # Important background tasks (learning, caching)
    MEDIUM = 3      # Optimization, analytics
    LOW = 4         # Maintenance, cleanup
    IDLE = 5        # Run when nothing else is happening


class ThreadState(Enum):
    """Thread lifecycle states"""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    WAITING = "waiting"


@dataclass
class ThreadInfo:
    """Information about a managed thread"""
    thread_id: str
    name: str
    category: str  # 'core', 'phase1-5', 'advanced', 'agi', 'monitoring'
    priority: ThreadPriority
    state: ThreadState
    thread: Optional[threading.Thread]
    task_queue: queue.Queue
    created_at: datetime
    started_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    
    def success_rate(self) -> float:
        """Calculate task success rate"""
        total = self.tasks_completed + self.tasks_failed
        if total == 0:
            return 1.0
        return self.tasks_completed / total


@dataclass
class ThreadTask:
    """A task to be executed by a thread"""
    task_id: str
    function: Callable
    args: tuple
    kwargs: dict
    priority: ThreadPriority
    created_at: datetime
    timeout: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    callback: Optional[Callable] = None
    error_callback: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ThreadManager:
    """
    Centralized thread management system with autonomous decision-making
    
    The brain uses this to manage all module threads intelligently:
    - Create/destroy threads based on workload
    - Prioritize critical tasks
    - Monitor thread health
    - Optimize resource allocation
    - Self-healing (restart failed threads)
    """
    
    def __init__(self, max_threads: int = 50, enable_auto_scaling: bool = True):
        """
        Initialize thread manager
        
        Args:
            max_threads: Maximum concurrent threads
            enable_auto_scaling: Enable autonomous thread scaling
        """
        self.max_threads = max_threads
        self.enable_auto_scaling = enable_auto_scaling
        
        # Thread registry
        self.threads: Dict[str, ThreadInfo] = {}
        self.thread_lock = threading.RLock()
        
        # Category-based thread pools
        self.categories = {
            'core': {'max_threads': 10, 'threads': set()},
            'phase1': {'max_threads': 5, 'threads': set()},  # Knowledge
            'phase2': {'max_threads': 5, 'threads': set()},  # Search
            'phase3': {'max_threads': 8, 'threads': set()},  # Web Intelligence
            'phase4': {'max_threads': 6, 'threads': set()},  # Code Execution
            'phase5': {'max_threads': 4, 'threads': set()},  # Optimization
            'advanced': {'max_threads': 8, 'threads': set()},  # Advanced features
            'agi': {'max_threads': 6, 'threads': set()},     # AGI components
            'monitoring': {'max_threads': 3, 'threads': set()}  # Health checks
        }
        
        # Global task queue with priority
        self.global_queue: queue.PriorityQueue = queue.PriorityQueue()
        
        # Statistics
        self.stats = {
            'total_threads_created': 0,
            'total_tasks_completed': 0,
            'total_tasks_failed': 0,
            'threads_auto_scaled': 0,
            'threads_restarted': 0,
            'uptime_start': datetime.now()
        }
        
        # Autonomous decision system
        self.decision_system = ThreadDecisionSystem(self)
        
        # Start monitoring thread
        self._start_monitoring()
        
        logger.info(f"🧵 ThreadManager initialized (max: {max_threads}, auto-scaling: {enable_auto_scaling})")
    
    def create_thread(
        self,
        name: str,
        category: str,
        function: Callable,
        priority: ThreadPriority = ThreadPriority.MEDIUM,
        daemon: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new managed thread
        
        Args:
            name: Thread name
            category: Thread category (core, phase1-5, advanced, agi, monitoring)
            function: Function to execute in thread
            priority: Thread priority
            daemon: Whether thread is daemon
            metadata: Additional metadata
            
        Returns:
            Thread ID
        """
        with self.thread_lock:
            # Check if category can accept more threads
            if category in self.categories:
                category_info = self.categories[category]
                if len(category_info['threads']) >= category_info['max_threads']:
                    if not self.enable_auto_scaling:
                        raise RuntimeError(f"Category '{category}' has reached max threads")
                    logger.info(f"⚖️ Auto-scaling category '{category}'")
                    category_info['max_threads'] += 2
                    self.stats['threads_auto_scaled'] += 1
            
            # Create thread info
            thread_id = str(uuid.uuid4())[:8]
            task_queue = queue.Queue()
            
            thread_info = ThreadInfo(
                thread_id=thread_id,
                name=name,
                category=category,
                priority=priority,
                state=ThreadState.INITIALIZING,
                thread=None,
                task_queue=task_queue,
                created_at=datetime.now(),
                metadata=metadata or {}
            )
            
            # Create worker thread
            def worker():
                """Thread worker function"""
                thread_info.state = ThreadState.RUNNING
                thread_info.started_at = datetime.now()
                logger.debug(f"🧵 Thread '{name}' ({thread_id}) started")
                
                try:
                    # Execute main function
                    function(thread_info, task_queue)
                except Exception as e:
                    thread_info.state = ThreadState.ERROR
                    thread_info.errors.append(str(e))
                    logger.error(f"❌ Thread '{name}' ({thread_id}) error: {e}")
                finally:
                    thread_info.state = ThreadState.STOPPED
                    logger.debug(f"🧵 Thread '{name}' ({thread_id}) stopped")
            
            thread = threading.Thread(target=worker, name=name, daemon=daemon)
            thread_info.thread = thread
            
            # Register thread
            self.threads[thread_id] = thread_info
            if category in self.categories:
                self.categories[category]['threads'].add(thread_id)
            
            self.stats['total_threads_created'] += 1
            
            # Start thread
            thread.start()
            
            logger.info(f"✅ Created thread '{name}' ({thread_id}) in category '{category}'")
            return thread_id
    
    def submit_task(
        self,
        thread_id: str,
        function: Callable,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        priority: ThreadPriority = ThreadPriority.MEDIUM,
        timeout: Optional[float] = None,
        callback: Optional[Callable] = None
    ) -> str:
        """
        Submit a task to a specific thread
        
        Args:
            thread_id: Target thread ID
            function: Function to execute
            args: Function arguments
            kwargs: Function keyword arguments
            priority: Task priority
            timeout: Task timeout in seconds
            callback: Callback on success
            
        Returns:
            Task ID
        """
        if thread_id not in self.threads:
            raise ValueError(f"Thread '{thread_id}' not found")
        
        thread_info = self.threads[thread_id]
        
        # Create task
        task = ThreadTask(
            task_id=str(uuid.uuid4())[:8],
            function=function,
            args=args,
            kwargs=kwargs or {},
            priority=priority,
            created_at=datetime.now(),
            timeout=timeout,
            callback=callback
        )
        
        # Add to thread's queue
        thread_info.task_queue.put((priority.value, task))
        thread_info.last_activity = datetime.now()
        
        return task.task_id
    
    def submit_global_task(
        self,
        function: Callable,
        category: str,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        priority: ThreadPriority = ThreadPriority.MEDIUM
    ) -> str:
        """
        Submit task to global queue (will be picked by any thread in category)
        
        Args:
            function: Function to execute
            category: Target category
            args: Function arguments
            kwargs: Function keyword arguments
            priority: Task priority
            
        Returns:
            Task ID
        """
        task = ThreadTask(
            task_id=str(uuid.uuid4())[:8],
            function=function,
            args=args,
            kwargs=kwargs or {},
            priority=priority,
            created_at=datetime.now(),
            metadata={'category': category}
        )
        
        self.global_queue.put((priority.value, task))
        return task.task_id
    
    def get_thread_status(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific thread"""
        if thread_id not in self.threads:
            return None
        
        thread_info = self.threads[thread_id]
        return {
            'thread_id': thread_id,
            'name': thread_info.name,
            'category': thread_info.category,
            'state': thread_info.state.value,
            'priority': thread_info.priority.value,
            'tasks_completed': thread_info.tasks_completed,
            'tasks_failed': thread_info.tasks_failed,
            'success_rate': thread_info.success_rate(),
            'uptime': (datetime.now() - thread_info.started_at).total_seconds() if thread_info.started_at else 0,
            'queue_size': thread_info.task_queue.qsize(),
            'last_activity': thread_info.last_activity.isoformat() if thread_info.last_activity else None,
            'is_alive': thread_info.thread.is_alive() if thread_info.thread else False
        }
    
    def get_category_status(self, category: str) -> Dict[str, Any]:
        """Get status of all threads in a category"""
        if category not in self.categories:
            return {'error': f"Category '{category}' not found"}
        
        category_info = self.categories[category]
        thread_ids = list(category_info['threads'])
        
        threads = []
        for thread_id in thread_ids:
            if thread_id in self.threads:
                threads.append(self.get_thread_status(thread_id))
        
        return {
            'category': category,
            'max_threads': category_info['max_threads'],
            'active_threads': len([t for t in threads if t and t['is_alive']]),
            'total_threads': len(threads),
            'threads': threads
        }
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status"""
        with self.thread_lock:
            active_threads = sum(1 for t in self.threads.values() if t.thread and t.thread.is_alive())
            
            category_stats = {}
            for cat_name in self.categories:
                cat_status = self.get_category_status(cat_name)
                category_stats[cat_name] = {
                    'active': cat_status['active_threads'],
                    'total': cat_status['total_threads'],
                    'max': cat_status['max_threads']
                }
            
            return {
                'total_threads': len(self.threads),
                'active_threads': active_threads,
                'max_threads': self.max_threads,
                'auto_scaling': self.enable_auto_scaling,
                'categories': category_stats,
                'stats': self.stats,
                'uptime': (datetime.now() - self.stats['uptime_start']).total_seconds(),
                'global_queue_size': self.global_queue.qsize()
            }
    
    def pause_thread(self, thread_id: str):
        """Pause a thread (it will finish current task then wait)"""
        if thread_id in self.threads:
            self.threads[thread_id].state = ThreadState.PAUSED
            logger.info(f"⏸️ Thread '{thread_id}' paused")
    
    def resume_thread(self, thread_id: str):
        """Resume a paused thread"""
        if thread_id in self.threads:
            thread_info = self.threads[thread_id]
            if thread_info.state == ThreadState.PAUSED:
                thread_info.state = ThreadState.RUNNING
                logger.info(f"▶️ Thread '{thread_id}' resumed")
    
    def stop_thread(self, thread_id: str, timeout: float = 5.0):
        """Stop a thread gracefully"""
        if thread_id not in self.threads:
            return
        
        thread_info = self.threads[thread_id]
        thread_info.state = ThreadState.STOPPING
        
        # Wait for thread to finish
        if thread_info.thread:
            thread_info.thread.join(timeout=timeout)
        
        thread_info.state = ThreadState.STOPPED
        logger.info(f"🛑 Thread '{thread_id}' stopped")
    
    def restart_thread(self, thread_id: str):
        """Restart a failed thread"""
        if thread_id not in self.threads:
            return
        
        thread_info = self.threads[thread_id]
        old_name = thread_info.name
        category = thread_info.category
        priority = thread_info.priority
        metadata = thread_info.metadata.copy()
        
        # Stop old thread
        self.stop_thread(thread_id)
        
        # Create new thread with same configuration
        # Note: This requires the original function, which we need to store
        logger.info(f"🔄 Thread '{old_name}' ({thread_id}) marked for restart")
        self.stats['threads_restarted'] += 1
    
    def shutdown(self, timeout: float = 10.0):
        """Shutdown all threads gracefully"""
        logger.info("🛑 ThreadManager shutting down...")
        
        with self.thread_lock:
            thread_ids = list(self.threads.keys())
        
        for thread_id in thread_ids:
            self.stop_thread(thread_id, timeout=timeout/len(thread_ids))
        
        logger.info("✅ ThreadManager shutdown complete")
    
    def _start_monitoring(self):
        """Start monitoring thread for health checks and autonomous decisions"""
        def monitor_worker(thread_info: ThreadInfo, task_queue: queue.Queue):
            """Monitor all threads and make autonomous decisions"""
            while thread_info.state == ThreadState.RUNNING:
                try:
                    # Health check every 5 seconds
                    time.sleep(5)
                    
                    with self.thread_lock:
                        # Check for dead threads
                        for tid, tinfo in list(self.threads.items()):
                            if tinfo.thread and not tinfo.thread.is_alive() and tinfo.state == ThreadState.RUNNING:
                                logger.warning(f"⚠️ Thread '{tinfo.name}' ({tid}) died unexpectedly")
                                tinfo.state = ThreadState.ERROR
                                
                                # Autonomous decision: Restart critical threads
                                if tinfo.priority in [ThreadPriority.CRITICAL, ThreadPriority.HIGH]:
                                    logger.info(f"🔄 Auto-restarting critical thread '{tinfo.name}'")
                                    self.restart_thread(tid)
                        
                        # Autonomous decision: Scale down idle threads
                        if self.enable_auto_scaling:
                            for cat_name, cat_info in self.categories.items():
                                active = sum(1 for tid in cat_info['threads'] 
                                           if tid in self.threads and self.threads[tid].thread.is_alive())
                                
                                # If many threads idle, suggest scale-down
                                if active < cat_info['max_threads'] * 0.5 and cat_info['max_threads'] > 3:
                                    logger.debug(f"💡 Category '{cat_name}' underutilized (scale-down opportunity)")
                    
                    thread_info.last_activity = datetime.now()
                    thread_info.tasks_completed += 1
                    
                except Exception as e:
                    logger.error(f"❌ Monitoring error: {e}")
                    thread_info.tasks_failed += 1
        
        # Create monitoring thread
        self.create_thread(
            name="system_monitor",
            category="monitoring",
            function=monitor_worker,
            priority=ThreadPriority.HIGH,
            daemon=True
        )


class ThreadDecisionSystem:
    """
    Autonomous decision-making system for thread management
    
    The brain uses this to:
    - Decide when to create/destroy threads
    - Prioritize tasks intelligently
    - Optimize resource allocation
    - Self-heal from failures
    """
    
    def __init__(self, thread_manager: ThreadManager):
        self.thread_manager = thread_manager
        self.decisions_made = 0
        self.decision_history: List[Dict[str, Any]] = []
    
    def should_create_thread(self, category: str, current_load: float) -> bool:
        """
        Decide if a new thread should be created
        
        Args:
            category: Thread category
            current_load: Current workload (0.0-1.0)
            
        Returns:
            True if new thread should be created
        """
        if not self.thread_manager.enable_auto_scaling:
            return False
        
        # Create thread if load > 80%
        if current_load > 0.8:
            self._record_decision('create_thread', category, {'load': current_load})
            return True
        
        return False
    
    def should_scale_down(self, category: str, idle_time: float) -> bool:
        """
        Decide if threads should be scaled down
        
        Args:
            category: Thread category
            idle_time: Time in seconds threads have been idle
            
        Returns:
            True if scale-down recommended
        """
        # Scale down if idle for more than 5 minutes
        if idle_time > 300:
            self._record_decision('scale_down', category, {'idle_time': idle_time})
            return True
        
        return False
    
    def prioritize_tasks(self, tasks: List[ThreadTask]) -> List[ThreadTask]:
        """
        Intelligently prioritize tasks
        
        Args:
            tasks: List of tasks to prioritize
            
        Returns:
            Sorted list of tasks by priority
        """
        # Sort by priority, then by creation time
        return sorted(tasks, key=lambda t: (t.priority.value, t.created_at))
    
    def _record_decision(self, decision_type: str, context: str, data: Dict[str, Any]):
        """Record decision for learning"""
        self.decisions_made += 1
        self.decision_history.append({
            'decision_id': self.decisions_made,
            'type': decision_type,
            'context': context,
            'data': data,
            'timestamp': datetime.now().isoformat()
        })
        
        # Keep only last 1000 decisions
        if len(self.decision_history) > 1000:
            self.decision_history = self.decision_history[-1000:]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_worker_thread(
    thread_info: ThreadInfo,
    task_queue: queue.Queue,
    process_func: Callable[[Any], Any]
):
    """
    Generic worker thread that processes tasks from queue
    
    Args:
        thread_info: Thread information
        task_queue: Queue to pull tasks from
        process_func: Function to process each task
    """
    while thread_info.state == ThreadState.RUNNING:
        try:
            # Get task with timeout
            try:
                priority, task = task_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            
            # Check if paused
            while thread_info.state == ThreadState.PAUSED:
                time.sleep(0.5)
            
            # Stop if requested
            if thread_info.state == ThreadState.STOPPING:
                break
            
            # Execute task
            start_time = time.time()
            try:
                result = task.function(*task.args, **task.kwargs)
                
                # Call success callback
                if task.callback:
                    task.callback(result)
                
                thread_info.tasks_completed += 1
                thread_info.last_activity = datetime.now()
                
            except Exception as e:
                logger.error(f"❌ Task {task.task_id} failed: {e}")
                thread_info.tasks_failed += 1
                thread_info.errors.append(f"Task {task.task_id}: {str(e)}")
                
                # Retry logic
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    logger.info(f"🔄 Retrying task {task.task_id} ({task.retry_count}/{task.max_retries})")
                    task_queue.put((priority, task))
                elif task.error_callback:
                    task.error_callback(e)
            
            finally:
                task_queue.task_done()
                
        except Exception as e:
            logger.error(f"❌ Worker thread error: {e}")
            thread_info.errors.append(str(e))


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example: Create thread manager
    manager = ThreadManager(max_threads=20, enable_auto_scaling=True)
    
    # Example: Create a worker thread
    def example_worker(thread_info, task_queue):
        create_worker_thread(thread_info, task_queue, lambda x: print(f"Processing: {x}"))
    
    thread_id = manager.create_thread(
        name="example_worker",
        category="core",
        function=example_worker,
        priority=ThreadPriority.MEDIUM
    )
    
    # Submit tasks
    for i in range(10):
        manager.submit_task(
            thread_id,
            function=lambda x: print(f"Task {x}"),
            args=(i,),
            priority=ThreadPriority.MEDIUM
        )
    
    # Check status
    time.sleep(2)
    status = manager.get_system_status()
    print(f"System status: {status}")
    
    # Cleanup
    manager.shutdown()
