#!/usr/bin/env python3
"""
Test script for the intelligent caching system
Demonstrates how time-sensitive queries are automatically detected and cached appropriately
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api_wrapper import api_wrapper
import time

def test_time_sensitive_detection():
    """Test the time-sensitive query detection"""
    print("🧪 Testing Time-Sensitive Query Detection\n")
    
    test_queries = [
        # Financial queries (should get 1 day cache)
        "What is the current price of Bitcoin?",
        "GST rate for electronics in India",
        "Current USD to INR exchange rate",
        
        # Technical specs (should get 1 week cache)
        "iPhone 15 Pro specifications",
        "RTX 4090 technical specs",
        "Tesla Model S performance specs",
        
        # Current events (should get 1 hour cache)
        "Latest news about AI developments",
        "Current weather in Mumbai",
        "Recent updates from OpenAI",
        
        # General queries (should get default cache)
        "How to learn Python programming",
        "Explain quantum computing basics",
        "Best practices for web development"
    ]
    
    for query in test_queries:
        is_time_sensitive, category, duration = api_wrapper._is_time_sensitive_query(query)
        cache_duration = api_wrapper._get_intelligent_cache_duration(query)
        force_web = api_wrapper._should_force_web_search(query, [])
        
        hours = duration // 3600 if duration > 0 else cache_duration // 3600
        
        print(f"📝 Query: '{query}'")
        print(f"   ⏰ Time-sensitive: {is_time_sensitive}")
        if is_time_sensitive:
            print(f"   📂 Category: {category}")
            print(f"   🕒 Cache Duration: {hours} hours")
        print(f"   🔍 Force Web Search: {force_web}")
        print(f"   💾 Final Cache TTL: {cache_duration // 3600} hours")
        print()

def test_cache_statistics():
    """Test cache statistics functionality"""
    print("📊 Testing Cache Statistics\n")
    
    # Simulate some cached responses
    print("Simulating cache entries...")
    
    # Test with a price query (should auto-enable web search)
    print("Testing with a price query...")
    try:
        response = api_wrapper.generate_response(
            "What is the current price of iPhone 15 Pro in India?",
            category='general',
            tools=[],
            chat_history=[]
        )
        print(f"✅ Response generated: {len(response.content)} characters")
        print(f"🔍 Web search auto-enabled: {'web' in str(response.metadata)}")
    except Exception as e:
        print(f"❌ Error testing price query: {e}")
    
    # Get cache statistics
    stats = api_wrapper.get_cache_statistics()
    print(f"\n📈 Cache Statistics:")
    print(f"   Total Entries: {stats['total_entries']}")
    print(f"   Fresh: {stats['age_distribution']['fresh']}")
    print(f"   Medium: {stats['age_distribution']['medium']}")
    print(f"   Old: {stats['age_distribution']['old']}")
    print(f"   Expired: {stats['age_distribution']['expired']}")
    print(f"   Memory Usage: ~{stats['memory_usage']} bytes")
    
    # Test cleanup
    expired_count = api_wrapper.cleanup_expired_cache()
    print(f"   Cleaned up: {expired_count} expired entries")

def test_pattern_categories():
    """Display the configured time-sensitive patterns"""
    print("📋 Configured Time-Sensitive Categories\n")
    
    for category, config in api_wrapper.time_sensitive_patterns.items():
        hours = config['cache_duration'] // 3600
        print(f"📂 {category.upper()}:")
        print(f"   Description: {config['description']}")
        print(f"   Cache Duration: {hours} hours")
        print(f"   Patterns: {', '.join(config['patterns'][:5])}{'...' if len(config['patterns']) > 5 else ''}")
        print()

if __name__ == "__main__":
    print("🚀 Intelligent Caching System Test\n")
    print("=" * 60)
    
    test_pattern_categories()
    print("=" * 60)
    
    test_time_sensitive_detection()
    print("=" * 60)
    
    test_cache_statistics()
    print("=" * 60)
    
    print("✅ All tests completed!")
