"""
Monitoring System - Phase 5: Optimization

Real-time performance monitoring with metrics collection and alerting.
"""

import time
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime, timedelta
from enum import Enum
import statistics

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics"""
    COUNTER = "counter"      # Monotonically increasing (requests)
    GAUGE = "gauge"         # Point-in-time value (memory usage)
    HISTOGRAM = "histogram" # Distribution of values (latency)
    TIMER = "timer"         # Time duration measurements


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Metric:
    """Single metric measurement"""
    name: str
    type: MetricType
    value: float
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)
    
    def __str__(self) -> str:
        labels_str = ", ".join(f"{k}={v}" for k, v in self.labels.items())
        return f"{self.name}{{{labels_str}}} = {self.value}"


@dataclass
class Alert:
    """Performance alert"""
    level: AlertLevel
    message: str
    metric_name: str
    current_value: float
    threshold: float
    timestamp: float = field(default_factory=time.time)
    
    def __str__(self) -> str:
        return f"[{self.level.value.upper()}] {self.message} (value={self.current_value:.2f}, threshold={self.threshold:.2f})"


class MetricCollector:
    """
    Collects and aggregates metrics
    
    Features:
    - Multiple metric types (counter, gauge, histogram, timer)
    - Time-windowed statistics
    - Efficient storage with circular buffers
    """
    
    def __init__(self, window_size: int = 1000):
        """
        Initialize metric collector
        
        Args:
            window_size: Number of recent metrics to keep
        """
        self.metrics: Dict[str, deque] = {}
        self.window_size = window_size
        
        # Counters for quick access
        self.counters: Dict[str, float] = {}
        self.gauges: Dict[str, float] = {}
    
    def record_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """Record a counter metric (increments)"""
        labels = labels or {}
        
        # Update counter
        key = self._make_key(name, labels)
        self.counters[key] = self.counters.get(key, 0) + value
        
        # Record metric
        metric = Metric(
            name=name,
            type=MetricType.COUNTER,
            value=value,
            timestamp=time.time(),
            labels=labels
        )
        self._add_metric(key, metric)
    
    def record_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Record a gauge metric (current value)"""
        labels = labels or {}
        
        # Update gauge
        key = self._make_key(name, labels)
        self.gauges[key] = value
        
        # Record metric
        metric = Metric(
            name=name,
            type=MetricType.GAUGE,
            value=value,
            timestamp=time.time(),
            labels=labels
        )
        self._add_metric(key, metric)
    
    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Record a histogram metric (for distributions)"""
        labels = labels or {}
        
        metric = Metric(
            name=name,
            type=MetricType.HISTOGRAM,
            value=value,
            timestamp=time.time(),
            labels=labels
        )
        
        key = self._make_key(name, labels)
        self._add_metric(key, metric)
    
    def record_timer(self, name: str, duration: float, labels: Optional[Dict[str, str]] = None):
        """Record a timer metric (duration in seconds)"""
        labels = labels or {}
        
        metric = Metric(
            name=name,
            type=MetricType.TIMER,
            value=duration,
            timestamp=time.time(),
            labels=labels
        )
        
        key = self._make_key(name, labels)
        self._add_metric(key, metric)
    
    def _make_key(self, name: str, labels: Dict[str, str]) -> str:
        """Generate unique key for metric"""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    def _add_metric(self, key: str, metric: Metric):
        """Add metric to storage"""
        if key not in self.metrics:
            self.metrics[key] = deque(maxlen=self.window_size)
        self.metrics[key].append(metric)
    
    def get_statistics(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[Dict[str, float]]:
        """
        Get statistics for a metric
        
        Returns:
            Dictionary with min, max, avg, p50, p95, p99, count
        """
        labels = labels or {}
        key = self._make_key(name, labels)
        
        if key not in self.metrics or not self.metrics[key]:
            return None
        
        values = [m.value for m in self.metrics[key]]
        
        if not values:
            return None
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        return {
            'count': n,
            'min': min(values),
            'max': max(values),
            'avg': statistics.mean(values),
            'median': statistics.median(values),
            'p50': sorted_values[int(n * 0.50)],
            'p95': sorted_values[int(n * 0.95)] if n > 1 else sorted_values[0],
            'p99': sorted_values[int(n * 0.99)] if n > 1 else sorted_values[0],
            'stddev': statistics.stdev(values) if n > 1 else 0
        }
    
    def get_counter_value(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get current counter value"""
        key = self._make_key(name, labels or {})
        return self.counters.get(key, 0.0)
    
    def get_gauge_value(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Get current gauge value"""
        key = self._make_key(name, labels or {})
        return self.gauges.get(key)
    
    def get_all_metrics(self) -> Dict[str, List[Metric]]:
        """Get all metrics"""
        return {key: list(metrics) for key, metrics in self.metrics.items()}


class PerformanceMonitor:
    """
    Real-time performance monitoring system
    
    Features:
    - Metric collection (counter, gauge, histogram, timer)
    - Threshold-based alerting
    - Health checks
    - Performance reports
    """
    
    def __init__(self):
        """Initialize performance monitor"""
        self.collector = MetricCollector()
        self.alerts: List[Alert] = []
        self.alert_thresholds: Dict[str, Tuple[float, AlertLevel]] = {}
        
        # Health check functions
        self.health_checks: Dict[str, Callable[[], bool]] = {}
    
    # === Metric Recording ===
    
    def record_request(self, endpoint: str, duration: float, status: str = "success"):
        """Record an API request"""
        # Counter for total requests
        self.collector.record_counter(
            "requests_total",
            labels={"endpoint": endpoint, "status": status}
        )
        
        # Timer for request duration
        self.collector.record_timer(
            "request_duration",
            duration,
            labels={"endpoint": endpoint}
        )
        
        # Check thresholds
        self._check_threshold("request_duration", duration)
    
    def record_cache_hit(self, cache_name: str):
        """Record a cache hit"""
        self.collector.record_counter(
            "cache_hits",
            labels={"cache": cache_name}
        )
    
    def record_cache_miss(self, cache_name: str):
        """Record a cache miss"""
        self.collector.record_counter(
            "cache_misses",
            labels={"cache": cache_name}
        )
    
    def record_error(self, error_type: str, message: str):
        """Record an error"""
        self.collector.record_counter(
            "errors_total",
            labels={"type": error_type}
        )
        
        # Generate alert
        self.alerts.append(Alert(
            level=AlertLevel.ERROR,
            message=message,
            metric_name="errors_total",
            current_value=1,
            threshold=0
        ))
    
    def record_memory(self, bytes_used: float):
        """Record memory usage"""
        mb_used = bytes_used / (1024 * 1024)
        self.collector.record_gauge("memory_usage_mb", mb_used)
        self._check_threshold("memory_usage_mb", mb_used)
    
    def record_cpu(self, percent: float):
        """Record CPU usage"""
        self.collector.record_gauge("cpu_usage_percent", percent)
        self._check_threshold("cpu_usage_percent", percent)
    
    # === Threshold Management ===
    
    def set_threshold(self, metric_name: str, threshold: float, level: AlertLevel = AlertLevel.WARNING):
        """Set alert threshold for a metric"""
        self.alert_thresholds[metric_name] = (threshold, level)
    
    def _check_threshold(self, metric_name: str, value: float):
        """Check if metric exceeds threshold"""
        if metric_name not in self.alert_thresholds:
            return
        
        threshold, level = self.alert_thresholds[metric_name]
        
        if value > threshold:
            alert = Alert(
                level=level,
                message=f"{metric_name} exceeded threshold",
                metric_name=metric_name,
                current_value=value,
                threshold=threshold
            )
            self.alerts.append(alert)
            logger.warning(str(alert))
    
    # === Health Checks ===
    
    def register_health_check(self, name: str, check_func: Callable[[], bool]):
        """Register a health check function"""
        self.health_checks[name] = check_func
    
    def run_health_checks(self) -> Dict[str, bool]:
        """Run all health checks"""
        results = {}
        for name, check_func in self.health_checks.items():
            try:
                results[name] = check_func()
            except Exception as e:
                logger.error(f"Health check '{name}' failed: {e}")
                results[name] = False
        return results
    
    def is_healthy(self) -> bool:
        """Check if system is healthy"""
        results = self.run_health_checks()
        return all(results.values()) if results else True
    
    # === Reporting ===
    
    def get_cache_hit_rate(self, cache_name: str) -> float:
        """Calculate cache hit rate"""
        hits = self.collector.get_counter_value("cache_hits", {"cache": cache_name})
        misses = self.collector.get_counter_value("cache_misses", {"cache": cache_name})
        
        total = hits + misses
        return (hits / total * 100) if total > 0 else 0.0
    
    def get_request_stats(self, endpoint: str) -> Optional[Dict[str, float]]:
        """Get request statistics for an endpoint"""
        return self.collector.get_statistics(
            "request_duration",
            labels={"endpoint": endpoint}
        )
    
    def get_alerts(self, level: Optional[AlertLevel] = None) -> List[Alert]:
        """Get alerts, optionally filtered by level"""
        if level is None:
            return self.alerts
        return [a for a in self.alerts if a.level == level]
    
    def clear_alerts(self):
        """Clear all alerts"""
        self.alerts.clear()
    
    def generate_report(self) -> str:
        """Generate performance report"""
        report = []
        report.append("=" * 90)
        report.append("PERFORMANCE MONITORING REPORT")
        report.append("=" * 90)
        report.append("")
        
        # System metrics
        report.append("System Metrics:")
        report.append("-" * 90)
        
        memory = self.collector.get_gauge_value("memory_usage_mb")
        if memory is not None:
            report.append(f"  Memory Usage: {memory:.1f} MB")
        
        cpu = self.collector.get_gauge_value("cpu_usage_percent")
        if cpu is not None:
            report.append(f"  CPU Usage: {cpu:.1f}%")
        
        report.append("")
        
        # Request metrics
        report.append("Request Metrics:")
        report.append("-" * 90)
        
        # Get all request stats
        all_metrics = self.collector.get_all_metrics()
        request_metrics = {k: v for k, v in all_metrics.items() if k.startswith("request_duration")}
        
        for key, metrics in request_metrics.items():
            if metrics:
                stats = self.collector.get_statistics("request_duration", {})
                if stats:
                    report.append(f"  Endpoint: {key}")
                    report.append(f"    Count: {stats['count']}")
                    report.append(f"    Avg: {stats['avg']*1000:.2f}ms")
                    report.append(f"    P95: {stats['p95']*1000:.2f}ms")
                    report.append(f"    P99: {stats['p99']*1000:.2f}ms")
        
        report.append("")
        
        # Alerts
        if self.alerts:
            report.append("Recent Alerts:")
            report.append("-" * 90)
            for alert in self.alerts[-10:]:  # Last 10 alerts
                report.append(f"  {alert}")
            report.append("")
        
        report.append("=" * 90)
        
        return "\n".join(report)


# Global monitor instance
monitor = PerformanceMonitor()

# Set default thresholds
monitor.set_threshold("request_duration", 0.5, AlertLevel.WARNING)  # 500ms
monitor.set_threshold("memory_usage_mb", 500, AlertLevel.WARNING)   # 500MB
monitor.set_threshold("cpu_usage_percent", 80, AlertLevel.WARNING)  # 80%
