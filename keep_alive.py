#!/usr/bin/env python3
"""
Keep-Alive Service for Free Tier Cloud Deployments

Pings your deployed API every 10 minutes to prevent it from sleeping
(Railway/Render free tiers sleep after 15 minutes of inactivity)

Usage:
    python3 keep_alive.py https://your-app.railway.app your-api-key

Or run in background:
    nohup python3 keep_alive.py https://your-app.railway.app your-api-key &
"""

import sys
import time
import requests
from datetime import datetime
import argparse


def ping_api(base_url: str, api_key: str = None) -> bool:
    """
    Ping the API to keep it awake
    
    Args:
        base_url: Base URL of deployed API
        api_key: API key (optional for health endpoint)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Use health endpoint (no auth required)
        response = requests.get(f"{base_url}/health", timeout=30)
        
        if response.status_code == 200:
            health = response.json()
            uptime = health.get('uptime', 0)
            brain_status = health.get('brain_status', 'unknown')
            
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                  f"✅ Ping successful - Brain: {brain_status}, Uptime: {uptime:.0f}s")
            return True
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                  f"⚠️  Status {response.status_code}")
            return False
    
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
              f"❌ Ping failed: {e}")
        return False


def keep_alive(base_url: str, api_key: str = None, interval: int = 600):
    """
    Keep pinging the API at regular intervals
    
    Args:
        base_url: Base URL of deployed API
        api_key: API key (optional)
        interval: Ping interval in seconds (default: 600 = 10 minutes)
    """
    print("🔄 Keep-Alive Service Started")
    print(f"📍 Target: {base_url}")
    print(f"⏱️  Interval: {interval}s ({interval/60:.0f} minutes)")
    print(f"🛑 Press Ctrl+C to stop")
    print("-" * 60)
    
    consecutive_failures = 0
    
    try:
        while True:
            success = ping_api(base_url, api_key)
            
            if success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                
                if consecutive_failures >= 3:
                    print(f"\n⚠️  Warning: {consecutive_failures} consecutive failures!")
                    print("   Your API might be down. Check the deployment.")
            
            # Wait for next ping
            time.sleep(interval)
    
    except KeyboardInterrupt:
        print("\n\n🛑 Keep-Alive Service Stopped")
        print(f"   Total runtime: {time.time()}")


def main():
    parser = argparse.ArgumentParser(
        description="Keep your free-tier cloud deployment awake"
    )
    parser.add_argument(
        "base_url",
        help="Base URL of your deployed API (e.g., https://your-app.railway.app)"
    )
    parser.add_argument(
        "--api-key",
        help="API key for authentication (optional for health checks)",
        default=None
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=600,
        help="Ping interval in seconds (default: 600 = 10 minutes)"
    )
    
    args = parser.parse_args()
    
    # Validate URL
    base_url = args.base_url.rstrip('/')
    if not base_url.startswith('http'):
        print("❌ Error: Base URL must start with http:// or https://")
        sys.exit(1)
    
    # Start keep-alive service
    keep_alive(base_url, args.api_key, args.interval)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 keep_alive.py https://your-app.railway.app [api-key]")
        print("\nExample:")
        print("  python3 keep_alive.py https://companion-brain-production.up.railway.app")
        print("\nOr run in background:")
        print("  nohup python3 keep_alive.py https://your-app.railway.app &")
        sys.exit(1)
    
    main()
