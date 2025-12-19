#!/usr/bin/env python3
"""
Companion AI Performance Benchmark Suite
========================================

Comprehensive benchmarking for the Companion AI system including:
- Response time analysis
- Memory usage monitoring
- Tool execution performance
- Concurrent user simulation
- AI provider comparison
- Database performance
"""

import time
import psutil
import threading
import requests
import json
import statistics
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
import matplotlib.pyplot as plt
import numpy as np

# Add companion_baas to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from companion_baas.sdk import BrainClient


class PerformanceBenchmark:
    """Comprehensive performance benchmarking suite"""

    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        self.results = {}
        self.start_time = None
        self.end_time = None

        # Initialize brain client for direct testing
        self.brain_client = BrainClient(
            app_type="chatbot",
            enable_caching=True,
            enable_search=False,  # Disable for cleaner benchmarks
            enable_learning=False,
            enable_agi=False,
            enable_autonomy=False
        )

    def start_benchmark(self, name: str):
        """Start a benchmark measurement"""
        self.start_time = time.time()
        print(f"🚀 Starting benchmark: {name}")

    def end_benchmark(self, name: str) -> float:
        """End a benchmark measurement and return duration"""
        self.end_time = time.time()
        duration = self.end_time - self.start_time
        print(".2f"        self.results[name] = duration
        return duration

    def measure_memory_usage(self) -> Dict[str, float]:
        """Measure current memory usage"""
        process = psutil.Process()
        memory_info = process.memory_info()

        return {
            'rss': memory_info.rss / 1024 / 1024,  # MB
            'vms': memory_info.vms / 1024 / 1024,  # MB
            'percent': process.memory_percent()
        }

    def benchmark_api_response_time(self, num_requests: int = 50) -> Dict[str, Any]:
        """Benchmark API response times"""
        print(f"📊 Benchmarking API response times ({num_requests} requests)...")

        response_times = []
        memory_usage = []

        test_messages = [
            "Hello, how are you?",
            "What is the capital of France?",
            "Explain quantum computing in simple terms",
            "Write a Python function to calculate fibonacci numbers",
            "What are the benefits of renewable energy?",
        ]

        for i in range(num_requests):
            message = test_messages[i % len(test_messages)]

            start_time = time.time()
            try:
                response = requests.post(
                    f"{self.base_url}/api/chat",
                    json={"message": message, "user_id": f"benchmark_user_{i}"},
                    timeout=30
                )
                end_time = time.time()

                if response.status_code == 200:
                    response_times.append(end_time - start_time)
                    memory_usage.append(self.measure_memory_usage())
                    print(".2f"                else:
                    print(f"❌ Request {i+1} failed with status {response.status_code}")

            except Exception as e:
                print(f"❌ Request {i+1} failed: {e}")

        if response_times:
            return {
                'avg_response_time': statistics.mean(response_times),
                'min_response_time': min(response_times),
                'max_response_time': max(response_times),
                'median_response_time': statistics.median(response_times),
                'std_dev': statistics.stdev(response_times) if len(response_times) > 1 else 0,
                'total_requests': len(response_times),
                'success_rate': len(response_times) / num_requests * 100,
                'memory_usage': memory_usage[-1] if memory_usage else None
            }
        else:
            return {'error': 'No successful requests'}

    def benchmark_brain_direct(self, num_requests: int = 20) -> Dict[str, Any]:
        """Benchmark brain client directly (bypassing API)"""
        print(f"🧠 Benchmarking brain client directly ({num_requests} requests)...")

        response_times = []
        memory_usage = []

        test_messages = [
            "Hello!",
            "What is AI?",
            "Calculate 15 + 27",
            "What day is today?",
            "Reverse this list: [1, 2, 3, 4, 5]"
        ]

        for i in range(num_requests):
            message = test_messages[i % len(test_messages)]

            start_time = time.time()
            try:
                response = self.brain_client.ask(message, user_id=f"direct_test_{i}")
                end_time = time.time()

                response_times.append(end_time - start_time)
                memory_usage.append(self.measure_memory_usage())

                print(".2f"
            except Exception as e:
                print(f"❌ Direct brain call {i+1} failed: {e}")

        if response_times:
            return {
                'avg_response_time': statistics.mean(response_times),
                'min_response_time': min(response_times),
                'max_response_time': max(response_times),
                'median_response_time': statistics.median(response_times),
                'std_dev': statistics.stdev(response_times) if len(response_times) > 1 else 0,
                'total_requests': len(response_times),
                'memory_usage': memory_usage[-1] if memory_usage else None
            }
        else:
            return {'error': 'No successful brain calls'}

    def benchmark_tools_execution(self) -> Dict[str, Any]:
        """Benchmark tool execution performance"""
        print("🔧 Benchmarking tool execution...")

        tool_tests = [
            ("add", [5, 3], 8),
            ("subtract", [10, 4], 6),
            ("multiply", [7, 6], 42),
            ("power", [2, 8], 256),
            ("word_count", ["Hello world this is a test"], 6),
            ("uppercase", ["hello world"], "HELLO WORLD"),
            ("current_date", [], None),  # Dynamic result
            ("list_length", [[1, 2, 3, 4, 5]], 5),
        ]

        results = {}

        for tool_name, args, expected in tool_tests:
            try:
                start_time = time.time()
                result = self.brain_client.execute_tool(tool_name, *args)
                end_time = time.time()

                execution_time = end_time - start_time

                # Check result if expected value provided
                if expected is not None:
                    success = result == expected
                else:
                    success = result is not None

                results[tool_name] = {
                    'execution_time': execution_time,
                    'success': success,
                    'result': result,
                    'expected': expected
                }

                status = "✅" if success else "❌"
                print(".3f"
            except Exception as e:
                results[tool_name] = {
                    'execution_time': 0,
                    'success': False,
                    'error': str(e)
                }
                print(f"❌ Tool {tool_name}: Failed - {e}")

        return results

    def benchmark_concurrent_users(self, num_users: int = 10, requests_per_user: int = 5) -> Dict[str, Any]:
        """Benchmark concurrent user simulation"""
        print(f"👥 Benchmarking concurrent users ({num_users} users, {requests_per_user} requests each)...")

        results = []
        errors = []

        def user_simulation(user_id: int):
            """Simulate a single user making requests"""
            user_results = []

            for req_id in range(requests_per_user):
                try:
                    start_time = time.time()
                    response = requests.post(
                        f"{self.base_url}/api/chat",
                        json={
                            "message": f"User {user_id} request {req_id}: Hello!",
                            "user_id": f"concurrent_user_{user_id}"
                        },
                        timeout=30
                    )
                    end_time = time.time()

                    if response.status_code == 200:
                        user_results.append(end_time - start_time)
                    else:
                        errors.append(f"User {user_id} req {req_id}: HTTP {response.status_code}")

                except Exception as e:
                    errors.append(f"User {user_id} req {req_id}: {e}")

            results.extend(user_results)

        # Start concurrent users
        threads = []
        for user_id in range(num_users):
            thread = threading.Thread(target=user_simulation, args=(user_id,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        if results:
            return {
                'total_requests': len(results),
                'successful_requests': len(results),
                'failed_requests': len(errors),
                'avg_response_time': statistics.mean(results),
                'min_response_time': min(results),
                'max_response_time': max(results),
                'median_response_time': statistics.median(results),
                'errors': errors[:10]  # First 10 errors
            }
        else:
            return {'error': 'No successful concurrent requests', 'errors': errors}

    def benchmark_memory_usage_over_time(self, duration_seconds: int = 60) -> Dict[str, Any]:
        """Monitor memory usage over time"""
        print(f"📈 Monitoring memory usage for {duration_seconds} seconds...")

        memory_readings = []
        start_time = time.time()

        while time.time() - start_time < duration_seconds:
            memory_readings.append(self.measure_memory_usage())
            time.sleep(1)  # Sample every second

        if memory_readings:
            rss_values = [r['rss'] for r in memory_readings]
            vms_values = [r['vms'] for r in memory_readings]
            percent_values = [r['percent'] for r in memory_readings]

            return {
                'duration': duration_seconds,
                'samples': len(memory_readings),
                'rss_mb': {
                    'avg': statistics.mean(rss_values),
                    'min': min(rss_values),
                    'max': max(rss_values),
                    'std_dev': statistics.stdev(rss_values) if len(rss_values) > 1 else 0
                },
                'vms_mb': {
                    'avg': statistics.mean(vms_values),
                    'min': min(vms_values),
                    'max': max(vms_values),
                    'std_dev': statistics.stdev(vms_values) if len(vms_values) > 1 else 0
                },
                'memory_percent': {
                    'avg': statistics.mean(percent_values),
                    'min': min(percent_values),
                    'max': max(percent_values),
                    'std_dev': statistics.stdev(percent_values) if len(percent_values) > 1 else 0
                }
            }
        else:
            return {'error': 'No memory readings collected'}

    def run_full_benchmark_suite(self) -> Dict[str, Any]:
        """Run the complete benchmark suite"""
        print("🏁 Starting Full Performance Benchmark Suite")
        print("=" * 60)

        benchmark_results = {
            'timestamp': datetime.now().isoformat(),
            'system_info': {
                'cpu_count': psutil.cpu_count(),
                'cpu_count_logical': psutil.cpu_count(logical=True),
                'memory_total_gb': psutil.virtual_memory().total / 1024 / 1024 / 1024,
                'python_version': sys.version
            }
        }

        # 1. API Response Time Benchmark
        print("\n1️⃣ API Response Time Benchmark")
        benchmark_results['api_response_time'] = self.benchmark_api_response_time(30)

        # 2. Direct Brain Performance
        print("\n2️⃣ Direct Brain Client Performance")
        benchmark_results['brain_direct'] = self.benchmark_brain_direct(20)

        # 3. Tool Execution Performance
        print("\n3️⃣ Tool Execution Performance")
        benchmark_results['tool_execution'] = self.benchmark_tools_execution()

        # 4. Concurrent Users Simulation
        print("\n4️⃣ Concurrent Users Simulation")
        benchmark_results['concurrent_users'] = self.benchmark_concurrent_users(5, 3)

        # 5. Memory Usage Monitoring
        print("\n5️⃣ Memory Usage Monitoring")
        benchmark_results['memory_usage'] = self.benchmark_memory_usage_over_time(30)

        # Calculate overall performance score
        benchmark_results['performance_score'] = self.calculate_performance_score(benchmark_results)

        print("\n🏁 Benchmark Suite Complete!")
        print("=" * 60)

        return benchmark_results

    def calculate_performance_score(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate an overall performance score"""
        score = 0
        max_score = 0

        # API Response Time (faster is better)
        if 'api_response_time' in results and 'avg_response_time' in results['api_response_time']:
            api_time = results['api_response_time']['avg_response_time']
            if api_time < 1.0:
                score += 10
            elif api_time < 2.0:
                score += 7
            elif api_time < 5.0:
                score += 4
            max_score += 10

        # Tool Execution (all tools working)
        if 'tool_execution' in results:
            tool_results = results['tool_execution']
            successful_tools = sum(1 for tool in tool_results.values() if tool.get('success', False))
            total_tools = len(tool_results)
            score += (successful_tools / total_tools) * 10
            max_score += 10

        # Memory Usage (lower is better)
        if 'memory_usage' in results and 'rss_mb' in results['memory_usage']:
            avg_memory = results['memory_usage']['rss_mb']['avg']
            if avg_memory < 100:  # Less than 100MB
                score += 10
            elif avg_memory < 200:
                score += 7
            elif avg_memory < 500:
                score += 4
            max_score += 10

        # Concurrent Performance
        if 'concurrent_users' in results and results['concurrent_users'].get('successful_requests', 0) > 0:
            success_rate = results['concurrent_users']['successful_requests'] / results['concurrent_users']['total_requests']
            score += success_rate * 10
            max_score += 10

        return {
            'score': score,
            'max_score': max_score,
            'percentage': (score / max_score * 100) if max_score > 0 else 0,
            'grade': self.get_performance_grade(score, max_score)
        }

    def get_performance_grade(self, score: float, max_score: float) -> str:
        """Convert score to letter grade"""
        percentage = (score / max_score * 100) if max_score > 0 else 0

        if percentage >= 90:
            return 'A+'
        elif percentage >= 80:
            return 'A'
        elif percentage >= 70:
            return 'B'
        elif percentage >= 60:
            return 'C'
        elif percentage >= 50:
            return 'D'
        else:
            return 'F'

    def save_results(self, results: Dict[str, Any], filename: str = None):
        """Save benchmark results to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"benchmark_results_{timestamp}.json"

        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        print(f"💾 Results saved to: {filename}")
        return filename

    def print_summary(self, results: Dict[str, Any]):
        """Print a formatted summary of results"""
        print("\n📊 PERFORMANCE BENCHMARK SUMMARY")
        print("=" * 50)

        if 'performance_score' in results:
            score = results['performance_score']
            print("🎯 Overall Performance Score:")
            print(".1f")
            print(f"   Grade: {score['grade']}")

        # API Performance
        if 'api_response_time' in results:
            api = results['api_response_time']
            if 'avg_response_time' in api:
                print("\n🚀 API Response Time:")
                print(".2f")
                print(".2f")
                print(".2f")
        # Tool Performance
        if 'tool_execution' in results:
            tools = results['tool_execution']
            successful = sum(1 for t in tools.values() if t.get('success', False))
            total = len(tools)
            print("\n🔧 Tool Execution:")
            print(f"   Success Rate: {successful}/{total} ({successful/total*100:.1f}%)")

        # Memory Usage
        if 'memory_usage' in results:
            mem = results['memory_usage']
            if 'rss_mb' in mem:
                print("\n💾 Memory Usage:")
                print(".1f")
                print(".1f")
        # Concurrent Users
        if 'concurrent_users' in results:
            conc = results['concurrent_users']
            if 'total_requests' in conc:
                success_rate = conc.get('successful_requests', 0) / conc['total_requests'] * 100
                print("\n👥 Concurrent Users:")
                print(".2f")
                print(".1f")
def main():
    """Main benchmark execution"""
    print("🤖 Companion AI Performance Benchmark Suite")
    print("==========================================")

    # Check if server is running
    try:
        response = requests.get("http://localhost:5000", timeout=5)
        if response.status_code != 200:
            print("❌ Server not responding. Please start the server first:")
            print("   python website/chat-backend-baas.py")
            return
    except:
        print("❌ Cannot connect to server. Please start the server first:")
        print("   python website/chat-backend-baas.py")
        return

    # Run benchmarks
    benchmark = PerformanceBenchmark()

    try:
        results = benchmark.run_full_benchmark_suite()

        # Save and display results
        filename = benchmark.save_results(results)
        benchmark.print_summary(results)

        print(f"\n📄 Detailed results saved to: {filename}")
        print("\n🎉 Benchmark complete! Use the results to optimize performance.")

    except KeyboardInterrupt:
        print("\n⏹️  Benchmark interrupted by user")
    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()