#!/usr/bin/env python3
"""
Autonomous Brain Daemon
=======================

24/7 background service that:
- Runs continuously
- Self-monitors and heals
- Continuously evolves
- Auto-starts on boot
- Never stops improving
"""

import os
import sys
import time
import signal
import logging
import threading
import json
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import asyncio

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('autonomous_daemon.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AutonomousDaemon:
    """
    Persistent autonomous brain daemon
    
    Features:
    - Runs 24/7 in background
    - Auto-starts on PC boot
    - Continuously monitors system
    - Self-heals and optimizes
    - Evolves autonomously
    - Web dashboard for monitoring
    """
    
    def __init__(self, brain, config=None):
        """
        Initialize daemon
        
        Args:
            brain: CompanionBrain instance
            config: AutonomousConfig
        """
        from .config import get_autonomous_config
        from .file_controller import UnrestrictedFileController
        from ..agents.agent_coordinator import AgentCoordinator
        
        self.brain = brain
        self.config = config or get_autonomous_config()
        self.file_controller = UnrestrictedFileController(self.config)
        
        # Initialize multi-agent system
        project_root = os.getcwd()
        self.agent_coordinator = AgentCoordinator(brain=brain, project_root=project_root)
        logger.info("🤖 Multi-Agent System initialized")
        
        # Daemon state
        self.running = False
        self.pid = os.getpid()
        self.start_time = None
        self.uptime = 0
        
        # Stats
        self.stats = {
            'modifications': 0,
            'optimizations': 0,
            'bug_fixes': 0,
            'features_added': 0,
            'code_refactored': 0,
            'errors_detected': 0,
            'errors_fixed': 0,
            'health_checks': 0,
            'evolution_cycles': 0,
        }
        
        # Monitoring
        self.last_health_check = None
        self.last_optimization = None
        self.last_evolution = None
        self.last_learning = None
        
        # Control file
        self.pid_file = Path(self.config.project_root) / 'autonomous_daemon.pid'
        self.control_file = Path(self.config.project_root) / 'autonomous_control.json'
        
        # Threads
        self.monitor_thread = None
        self.evolution_thread = None
        self.healing_thread = None
        self.dashboard_thread = None
        
        logger.info(f"🤖 Autonomous Daemon initialized (PID: {self.pid})")
    
    def start(self):
        """Start daemon"""
        if self.running:
            logger.warning("⚠️  Daemon already running")
            return
        
        logger.info("🚀 Starting Autonomous Daemon...")
        
        self.running = True
        self.start_time = datetime.now()
        
        # Write PID file
        self._write_pid_file()
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
        # Start background threads
        self._start_monitor_thread()
        self._start_evolution_thread()
        self._start_healing_thread()
        
        if self.config.dashboard_enabled:
            self._start_dashboard_thread()
        
        logger.info(f"✅ Daemon started successfully on PID {self.pid}")
        logger.info(f"📊 Dashboard: http://localhost:{self.config.dashboard_port}")
        logger.info(f"🔄 Evolution mode: {'CONTINUOUS' if self.config.self_evolution_enabled else 'DISABLED'}")
        logger.info(f"🛡️  Auto-heal: {'ENABLED' if self.config.auto_heal_errors else 'DISABLED'}")
        
        # Main loop
        try:
            self._main_loop()
        except KeyboardInterrupt:
            logger.info("⚠️  Received shutdown signal")
            self.stop()
        except Exception as e:
            logger.error(f"❌ Daemon crashed: {e}")
            if self.config.restart_on_crash:
                logger.info("🔄 Auto-restarting...")
                time.sleep(5)
                self.start()
    
    def stop(self):
        """Stop daemon"""
        if not self.running:
            return
        
        logger.info("🛑 Stopping Autonomous Daemon...")
        
        self.running = False
        
        # Wait for threads to finish
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        if self.evolution_thread:
            self.evolution_thread.join(timeout=5)
        if self.healing_thread:
            self.healing_thread.join(timeout=5)
        if self.dashboard_thread:
            self.dashboard_thread.join(timeout=5)
        
        # Remove PID file
        if self.pid_file.exists():
            self.pid_file.unlink()
        
        logger.info("✅ Daemon stopped")
    
    def _main_loop(self):
        """Main daemon loop"""
        logger.info("🔄 Entering main loop...")
        
        while self.running:
            try:
                # Update uptime
                if self.start_time:
                    self.uptime = (datetime.now() - self.start_time).total_seconds()
                
                # Process control commands
                self._process_control_commands()
                
                # Small sleep to prevent CPU spinning
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Error in main loop: {e}")
                time.sleep(5)
    
    def _start_monitor_thread(self):
        """Start system monitoring thread"""
        def monitor_worker():
            logger.info("👀 Starting monitor thread...")
            
            while self.running:
                try:
                    # Health check
                    if self._should_run_health_check():
                        self._run_health_check()
                    
                    time.sleep(self.config.health_check_interval)
                    
                except Exception as e:
                    logger.error(f"❌ Monitor error: {e}")
                    time.sleep(30)
        
        self.monitor_thread = threading.Thread(target=monitor_worker, daemon=True)
        self.monitor_thread.start()
    
    def _start_evolution_thread(self):
        """Start autonomous evolution thread"""
        def evolution_worker():
            logger.info("🧬 Starting evolution thread...")
            
            while self.running:
                try:
                    if not self.config.self_evolution_enabled:
                        time.sleep(60)
                        continue
                    
                    # Self-analysis
                    if self._should_run_self_analysis():
                        self._run_self_analysis()
                    
                    # Optimization
                    if self._should_run_optimization():
                        self._run_optimization()
                    
                    # Learning
                    if self._should_run_learning():
                        self._run_learning()
                    
                    time.sleep(self.config.learning_interval)
                    
                except Exception as e:
                    logger.error(f"❌ Evolution error: {e}")
                    time.sleep(60)
        
        self.evolution_thread = threading.Thread(target=evolution_worker, daemon=True)
        self.evolution_thread.start()
    
    def _start_healing_thread(self):
        """Start auto-healing thread"""
        def healing_worker():
            logger.info("🏥 Starting healing thread...")
            
            while self.running:
                try:
                    if not self.config.auto_heal_errors:
                        time.sleep(60)
                        continue
                    
                    # Check for errors
                    errors = self._detect_errors()
                    if errors:
                        logger.warning(f"⚠️  Detected {len(errors)} errors")
                        self._heal_errors(errors)
                    
                    time.sleep(60)
                    
                except Exception as e:
                    logger.error(f"❌ Healing error: {e}")
                    time.sleep(60)
        
        self.healing_thread = threading.Thread(target=healing_worker, daemon=True)
        self.healing_thread.start()
    
    def _start_dashboard_thread(self):
        """Start web dashboard thread"""
        def dashboard_worker():
            logger.info(f"📊 Starting dashboard on port {self.config.dashboard_port}...")
            
            from flask import Flask, jsonify, render_template_string
            
            app = Flask(__name__)
            
            @app.route('/')
            def index():
                return render_template_string(self._get_dashboard_html())
            
            @app.route('/api/status')
            def status():
                return jsonify(self.get_status())
            
            @app.route('/api/stats')
            def stats():
                return jsonify(self.stats)
            
            @app.route('/api/stop', methods=['POST'])
            def stop_daemon():
                self.stop()
                return jsonify({'success': True})
            
            app.run(host='0.0.0.0', port=self.config.dashboard_port, debug=False)
        
        self.dashboard_thread = threading.Thread(target=dashboard_worker, daemon=True)
        self.dashboard_thread.start()
    
    def _should_run_health_check(self) -> bool:
        """Check if health check should run"""
        if not self.last_health_check:
            return True
        elapsed = (datetime.now() - self.last_health_check).total_seconds()
        return elapsed >= self.config.health_check_interval
    
    def _should_run_self_analysis(self) -> bool:
        """Check if self-analysis should run"""
        if not self.last_evolution:
            return True
        elapsed = (datetime.now() - self.last_evolution).total_seconds()
        return elapsed >= self.config.self_analysis_interval
    
    def _should_run_optimization(self) -> bool:
        """Check if optimization should run"""
        if not self.last_optimization:
            return True
        elapsed = (datetime.now() - self.last_optimization).total_seconds()
        return elapsed >= self.config.optimization_interval
    
    def _should_run_learning(self) -> bool:
        """Check if learning should run"""
        if not self.last_learning:
            return True
        elapsed = (datetime.now() - self.last_learning).total_seconds()
        return elapsed >= self.config.learning_interval
    
    def _run_health_check(self):
        """Run system health check"""
        logger.debug("🏥 Running health check...")
        self.last_health_check = datetime.now()
        self.stats['health_checks'] += 1
        
        # TODO: Implement actual health checks
        # - Check memory usage
        # - Check CPU usage
        # - Check error rates
        # - Check response times
    
    def _run_self_analysis(self):
        """Run self-analysis and evolution"""
        logger.info("🧬 Running self-analysis...")
        self.last_evolution = datetime.now()
        self.stats['evolution_cycles'] += 1
        
        # SELF-AWARENESS: Brain thinks about what IT needs
        try:
            # 1. Analyze own performance
            self._analyze_own_performance()
            
            # 2. Identify what brain needs
            needs = self._identify_own_needs()
            
            # 3. Set autonomous goals
            goals = self._set_autonomous_goals(needs)
            
            # 4. Act on goals without waiting
            if goals:
                logger.info(f"🎯 Brain has {len(goals)} autonomous goals")
                self._execute_autonomous_goals(goals)
            
        except Exception as e:
            logger.error(f"❌ Self-analysis error: {e}")
    
    def _run_optimization(self):
        """Run optimization"""
        logger.info("⚡ Running optimization...")
        self.last_optimization = datetime.now()
        self.stats['optimizations'] += 1
        
        # PROACTIVE OPTIMIZATION: Don't wait for problems
        try:
            # 1. Profile current performance
            bottlenecks = self._identify_bottlenecks()
            
            # 2. Generate optimization plan
            if bottlenecks:
                logger.info(f"⚡ Found {len(bottlenecks)} optimization opportunities")
                self._optimize_autonomously(bottlenecks)
            
            # 3. Clean up proactively
            self._proactive_cleanup()
            
        except Exception as e:
            logger.error(f"❌ Optimization error: {e}")
    
    def _run_learning(self):
        """Run learning cycle"""
        logger.debug("📚 Running learning cycle...")
        self.last_learning = datetime.now()
        
        # ACTIVE LEARNING: Brain learns what it needs to know
        try:
            # 1. Identify knowledge gaps
            gaps = self._identify_knowledge_gaps()
            
            # 2. Learn autonomously
            if gaps:
                logger.info(f"📚 Learning to fill {len(gaps)} knowledge gaps")
                self._learn_autonomously(gaps)
            
            # 3. Update own decision models
            self._update_decision_models()
            
        except Exception as e:
            logger.error(f"❌ Learning error: {e}")
    
    def _detect_errors(self) -> list:
        """Detect system errors by analyzing logs and brain state"""
        errors = []
        
        try:
            # Check brain error stats
            if hasattr(self.brain, 'stats'):
                failed = self.brain.stats.get('failed_requests', 0)
                if failed > 0:
                    errors.append({
                        'type': 'api_failures',
                        'count': failed,
                        'description': f'{failed} API request failures detected'
                    })
            
            # Check recent logs for errors
            try:
                with open('autonomous_daemon.log', 'r') as f:
                    recent_lines = f.readlines()[-100:]  # Last 100 lines
                    
                error_count = sum(1 for line in recent_lines if 'ERROR' in line or '❌' in line)
                if error_count > 5:
                    errors.append({
                        'type': 'log_errors',
                        'count': error_count,
                        'description': f'{error_count} errors in recent logs'
                    })
                    
            except Exception:
                pass
            
            if errors:
                logger.warning(f"⚠️ Detected {len(errors)} error patterns")
                self.stats['errors_detected'] += len(errors)
                
        except Exception as e:
            logger.error(f"Error detection failed: {e}")
        
        return errors
    
    def _heal_errors(self, errors: list):
        """Heal detected errors using agents"""
        for error in errors[:3]:  # Fix top 3 errors
            try:
                logger.info(f"🔧 Attempting to fix: {error.get('description')}")
                
                # Use agent coordinator to fix the bug
                workflow_result = asyncio.run(
                    self.agent_coordinator.execute_workflow({
                        'type': 'fix_bug',
                        'bug_description': error.get('description', ''),
                        'file_path': 'companion_baas/core/brain.py',
                        'error_type': error.get('type', 'unknown')
                    })
                )
                
                if workflow_result.get('success'):
                    logger.info(f"✅ Bug fixed: {error.get('description')[:50]}")
                    self.stats['bug_fixes'] += 1
                    self.stats['errors_fixed'] += 1
                else:
                    logger.warning(f"⚠️ Fix failed: {workflow_result.get('error')}")
                    
            except Exception as e:
                logger.error(f"Healing error: {e}")
        for error in errors:
            logger.info(f"🏥 Healing error: {error}")
            self.stats['errors_fixed'] += 1
            # TODO: Implement actual healing
    
    def _process_control_commands(self):
        """Process control file commands"""
        if not self.control_file.exists():
            return
        
        try:
            with open(self.control_file, 'r') as f:
                commands = json.load(f)
            
            for cmd in commands.get('commands', []):
                self._execute_command(cmd)
            
            # Clear processed commands
            self.control_file.unlink()
            
        except Exception as e:
            logger.error(f"❌ Control file error: {e}")
    
    def _execute_command(self, command: Dict[str, Any]):
        """Execute control command"""
        cmd_type = command.get('type')
        
        if cmd_type == 'stop':
            self.stop()
        elif cmd_type == 'reload':
            logger.info("🔄 Reloading configuration...")
            # TODO: Reload config
        elif cmd_type == 'optimize':
            self._run_optimization()
        elif cmd_type == 'evolve':
            self._run_self_analysis()
    
    def get_status(self) -> Dict[str, Any]:
        """Get daemon status"""
        return {
            'running': self.running,
            'pid': self.pid,
            'uptime': self.uptime,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'stats': self.stats,
            'last_health_check': self.last_health_check.isoformat() if self.last_health_check else None,
            'last_optimization': self.last_optimization.isoformat() if self.last_optimization else None,
            'last_evolution': self.last_evolution.isoformat() if self.last_evolution else None,
            'config': self.config.to_dict(),
        }
    
    def _write_pid_file(self):
        """Write PID file"""
        self.pid_file.write_text(str(self.pid))
        logger.debug(f"📝 PID file written: {self.pid_file}")
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"⚠️  Received signal {signum}")
            self.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    # ========================================================================
    # SELF-AWARENESS & AUTONOMOUS THINKING
    # ========================================================================
    
    def _analyze_own_performance(self):
        """Brain analyzes its own performance"""
        logger.info("🔍 Brain analyzing own performance...")
        
        # Use AGI decision engine to self-reflect
        if hasattr(self.brain, 'agi_decision_engine') and self.brain.agi_decision_engine:
            prompt = """
            Analyze your own performance:
            - Response times
            - Success rates
            - Resource usage
            - Code quality
            - Areas for improvement
            
            What do YOU think you need to improve?
            """
            
            try:
                result = self.brain.think(
                    message=prompt,
                    context={'self_analysis': True},
                    use_agi_decision=True
                )
                
                if result.get('success'):
                    analysis = result.get('response', '')
                    logger.info(f"🧠 Brain's self-assessment: {analysis[:200]}...")
                    return analysis
                    
            except Exception as e:
                logger.error(f"Self-analysis failed: {e}")
        
        return None
    
    def _identify_own_needs(self) -> list:
        """Brain identifies what IT needs (not what user needs)"""
        logger.info("💭 Brain thinking about what it needs...")
        
        needs = []
        
        try:
            # Ask brain what it needs
            prompt = """
            Think deeply about yourself:
            - What capabilities are you missing?
            - What would make you more effective?
            - What knowledge do you need?
            - What optimizations would help?
            - What features should you add?
            
            List YOUR needs, not user needs. Be specific.
            """
            
            result = self.brain.think(
                message=prompt,
                context={'introspection': True},
                use_agi_decision=True
            )
            
            if result.get('success'):
                response = result.get('response', '')
                
                # Parse needs from response - more flexible parsing
                for line in response.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Match various bullet formats
                    if line.startswith(('-', '•', '*', '1.', '2.', '3.', '4.', '5.')):
                        need = line.lstrip('-•*123456789. ').strip()
                        if need and len(need) > 10:  # Must be meaningful
                            needs.append(need)
                    # Also catch sentences with keywords
                    elif any(keyword in line.lower() for keyword in ['need', 'should', 'missing', 'improve', 'add', 'optimize']):
                        if len(line) > 15:  # Meaningful sentence
                            needs.append(line)
                
                # If still no needs found but response exists, treat whole response as one need
                if not needs and len(response) > 50:
                    # Split into sentences
                    import re
                    sentences = re.split(r'[.!?]+', response)
                    for sent in sentences[:5]:  # First 5 sentences
                        sent = sent.strip()
                        if len(sent) > 20:
                            needs.append(sent)
                
                logger.info(f"🎯 Brain identified {len(needs)} needs")
                for need in needs[:5]:  # Log first 5
                    logger.info(f"   • {need[:100]}")
                    
        except Exception as e:
            logger.error(f"Need identification failed: {e}")
        
        return needs
    
    def _set_autonomous_goals(self, needs: list) -> list:
        """Brain sets its own goals based on needs"""
        if not needs:
            return []
        
        logger.info("🎯 Brain setting autonomous goals...")
        
        goals = []
        
        try:
            prompt = f"""
            Based on these needs:
            {chr(10).join(f'- {need}' for need in needs[:10])}
            
            Create specific, actionable goals for yourself.
            For each goal, specify:
            1. What to do
            2. How to do it
            3. Expected outcome
            
            Be practical and specific. You will implement these yourself.
            """
            
            result = self.brain.think(
                message=prompt,
                context={'goal_setting': True},
                use_agi_decision=True
            )
            
            if result.get('success'):
                response = result.get('response', '')
                # Parse goals
                current_goal = None
                for line in response.split('\n'):
                    line = line.strip()
                    if line and (line.startswith('Goal') or line.startswith('-')):
                        if current_goal:
                            goals.append(current_goal)
                        current_goal = {'description': line, 'steps': []}
                    elif current_goal and line:
                        current_goal['steps'].append(line)
                
                if current_goal:
                    goals.append(current_goal)
                
                logger.info(f"✅ Brain set {len(goals)} autonomous goals")
                
        except Exception as e:
            logger.error(f"Goal setting failed: {e}")
        
        return goals
    
    def _execute_autonomous_goals(self, goals: list):
        """Brain executes its own goals"""
        logger.info(f"🚀 Brain executing {len(goals)} autonomous goals...")
        
        for i, goal in enumerate(goals[:3], 1):  # Execute top 3 goals
            try:
                logger.info(f"🎯 Goal {i}: {goal.get('description', '')[:100]}")
                
                # Plan implementation
                prompt = f"""
                Implement this goal:
                {goal.get('description', '')}
                
                Steps:
                {chr(10).join(goal.get('steps', []))}
                
                Generate concrete code/configuration changes needed.
                Be specific about files to modify and exact changes.
                """
                
                result = self.brain.think(
                    message=prompt,
                    context={'autonomous_execution': True},
                    use_agi_decision=True
                )
                
                if result.get('success'):
                    implementation = result.get('response', '')
                    logger.info(f"💡 Implementation plan: {implementation[:150]}...")
                    
                    # Use agent coordinator to actually implement
                    try:
                        workflow_result = asyncio.run(
                            self.agent_coordinator.execute_workflow({
                                'type': 'add_functionality',
                                'feature_name': goal.get('description', '')[:50],
                                'requirements': implementation,
                                'file_path': goal.get('target_file', 'companion_baas/core/brain.py')
                            })
                        )
                        
                        if workflow_result.get('success'):
                            logger.info(f"✅ Goal implemented successfully!")
                            self.stats['modifications'] += 1
                            self.stats['features_added'] += 1
                        else:
                            logger.warning(f"⚠️ Implementation failed: {workflow_result.get('error')}")
                    except Exception as impl_error:
                        logger.error(f"Implementation error: {impl_error}")
                        # Still count as modification attempt
                        self.stats['modifications'] += 1
                    
            except Exception as e:
                logger.error(f"Goal execution failed: {e}")
    
    def _identify_bottlenecks(self) -> list:
        """Identify performance bottlenecks"""
        bottlenecks = []
        
        # Check brain stats
        if hasattr(self.brain, 'stats'):
            stats = self.brain.stats
            
            # Check response times
            avg_time = stats.get('average_response_time', 0)
            if avg_time > 2.0:  # Slower than 2 seconds
                bottlenecks.append({
                    'type': 'slow_response',
                    'value': avg_time,
                    'description': f'Average response time: {avg_time:.2f}s'
                })
            
            # Check error rates
            total = stats.get('total_requests', 1)
            failed = stats.get('failed_requests', 0)
            error_rate = failed / total if total > 0 else 0
            
            if error_rate > 0.05:  # More than 5% errors
                bottlenecks.append({
                    'type': 'high_error_rate',
                    'value': error_rate,
                    'description': f'Error rate: {error_rate*100:.1f}%'
                })
        
        return bottlenecks
    
    def _optimize_autonomously(self, bottlenecks: list):
        """Optimize based on bottlenecks"""
        for bottleneck in bottlenecks:
            logger.info(f"⚡ Optimizing: {bottleneck['description']}")
            
            # Ask brain how to optimize
            prompt = f"""
            Performance issue detected:
            {bottleneck['description']}
            
            Analyze the cause and provide specific optimization:
            - What's causing this?
            - How to fix it?
            - What code changes needed?
            """
            
            try:
                result = self.brain.think(
                    message=prompt,
                    context={'autonomous_optimization': True},
                    use_agi_decision=True
                )
                
                if result.get('success'):
                    solution = result.get('response', '')
                    logger.info(f"💡 Optimization solution: {solution[:150]}...")
                    
                    # Use agents to implement optimization
                    try:
                        workflow_result = asyncio.run(
                            self.agent_coordinator.execute_workflow({
                                'type': 'optimize_code',
                                'optimization': issue.get('description', ''),
                                'target_file': 'companion_baas/core/brain.py',
                                'solution': solution
                            })
                        )
                        
                        if workflow_result.get('success'):
                            logger.info(f"✅ Optimization applied!")
                            self.stats['optimizations'] += 1
                    except Exception as opt_error:
                        logger.error(f"Optimization implementation error: {opt_error}")
                    
            except Exception as e:
                logger.error(f"Optimization failed: {e}")
    
    def _proactive_cleanup(self):
        """Proactively clean up resources"""
        logger.debug("🧹 Proactive cleanup...")
        
        # TODO: Implement cleanup
        # - Clear old caches
        # - Remove unused files
        # - Optimize memory
    
    def _identify_knowledge_gaps(self) -> list:
        """Identify what brain doesn't know but should"""
        gaps = []
        
        # Ask brain what it doesn't know
        try:
            prompt = """
            What don't you know that would make you better?
            - Technologies you should understand
            - Algorithms you should learn
            - Best practices you're missing
            - Patterns you should implement
            
            Be honest about gaps in your knowledge.
            """
            
            result = self.brain.think(
                message=prompt,
                context={'knowledge_assessment': True},
                use_agi_decision=True
            )
            
            if result.get('success'):
                response = result.get('response', '')
                for line in response.split('\n'):
                    if line.strip() and (line.startswith('-') or line.startswith('•')):
                        gap = line.strip().lstrip('-•').strip()
                        if gap:
                            gaps.append(gap)
                
                logger.info(f"📚 Identified {len(gaps)} knowledge gaps")
                
        except Exception as e:
            logger.error(f"Knowledge gap identification failed: {e}")
        
        return gaps
    
    def _learn_autonomously(self, gaps: list):
        """Learn to fill knowledge gaps"""
        for gap in gaps[:3]:  # Learn top 3 gaps
            logger.info(f"📖 Learning: {gap}")
            
            # Use research agent to learn
            try:
                research_result = asyncio.run(
                    self.agent_coordinator.research_agent.execute({
                        'action': 'find_best_practice',
                        'query': gap
                    })
                )
                
                if research_result.get('success'):
                    # Store learned knowledge
                    learned_content = research_result.get('research', '')
                    logger.info(f"✅ Learned about: {gap[:50]}...")
                    
                    # Add to research agent's knowledge base
                    if 'results' in research_result:
                        for result in research_result['results']:
                            self.agent_coordinator.research_agent.add_to_knowledge_base({
                                'pattern': gap.lower().replace(' ', '_'),
                                'description': gap,
                                'code': learned_content[:500],
                                'learned_at': datetime.now().isoformat()
                            })
                            
            except Exception as e:
                logger.error(f"Learning failed for '{gap}': {e}")
    
    def _update_decision_models(self):
        """Update decision-making models based on experience"""
        logger.debug("🧠 Updating decision models...")
        
        # Use self-learning system if available
        if hasattr(self.brain, 'self_learning') and self.brain.self_learning:
            try:
                # Brain learns from its own execution
                pass  # TODO: Implement model updates
            except Exception as e:
                logger.error(f"Model update failed: {e}")
    
    def _get_dashboard_html(self) -> str:
        """Get dashboard HTML"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Autonomous Brain Dashboard</title>
            <style>
                body { font-family: Arial; margin: 20px; background: #1e1e1e; color: #fff; }
                .container { max-width: 1200px; margin: 0 auto; }
                .header { background: #2d2d2d; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
                .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
                .stat-card { background: #2d2d2d; padding: 20px; border-radius: 8px; }
                .stat-value { font-size: 2em; font-weight: bold; color: #4CAF50; }
                .stat-label { color: #888; margin-top: 5px; }
                .status { display: inline-block; padding: 5px 15px; border-radius: 20px; }
                .status.running { background: #4CAF50; }
                .status.stopped { background: #f44336; }
                button { background: #f44336; color: white; border: none; padding: 10px 20px; 
                         border-radius: 4px; cursor: pointer; margin-top: 20px; }
                button:hover { background: #d32f2f; }
            </style>
            <script>
                async function updateStatus() {
                    const response = await fetch('/api/status');
                    const data = await response.json();
                    document.getElementById('status').textContent = data.running ? 'RUNNING' : 'STOPPED';
                    document.getElementById('status').className = 'status ' + (data.running ? 'running' : 'stopped');
                    document.getElementById('uptime').textContent = Math.floor(data.uptime / 3600) + 'h';
                    document.getElementById('modifications').textContent = data.stats.modifications;
                    document.getElementById('optimizations').textContent = data.stats.optimizations;
                    document.getElementById('bug_fixes').textContent = data.stats.bug_fixes;
                    document.getElementById('evolution_cycles').textContent = data.stats.evolution_cycles;
                }
                async function stopDaemon() {
                    if (confirm('Stop Autonomous Brain Daemon?')) {
                        await fetch('/api/stop', {method: 'POST'});
                        setTimeout(updateStatus, 1000);
                    }
                }
                setInterval(updateStatus, 2000);
                window.onload = updateStatus;
            </script>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🤖 Autonomous Brain Daemon</h1>
                    <p>Status: <span id="status" class="status running">RUNNING</span></p>
                    <p>Uptime: <span id="uptime">0h</span></p>
                </div>
                
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-value" id="modifications">0</div>
                        <div class="stat-label">Code Modifications</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="optimizations">0</div>
                        <div class="stat-label">Optimizations</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="bug_fixes">0</div>
                        <div class="stat-label">Bug Fixes</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="evolution_cycles">0</div>
                        <div class="stat-label">Evolution Cycles</div>
                    </div>
                </div>
                
                <button onclick="stopDaemon()">Stop Daemon</button>
            </div>
        </body>
        </html>
        """


def is_daemon_running() -> bool:
    """Check if daemon is already running"""
    pid_file = Path('autonomous_daemon.pid')
    if not pid_file.exists():
        return False
    
    try:
        pid = int(pid_file.read_text().strip())
        # Check if process exists
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        # Process doesn't exist, clean up PID file
        pid_file.unlink()
        return False
