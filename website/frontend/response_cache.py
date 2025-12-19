"""
Smart Response Caching System
Caches API responses to reduce latency and API calls
"""

import hashlib
import json
import time
import threading
from typing import Optional, Dict, Any, Tuple
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)


class ResponseCache:
    """
    LRU cache with TTL for API responses
    Features:
    - Size-limited LRU eviction
    - Time-based expiration (TTL)
    - Thread-safe operations
    - Cache hit/miss statistics
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        """
        Initialize cache
        
        Args:
            max_size: Maximum number of cached items
            default_ttl: Default time-to-live in seconds (1 hour default)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: OrderedDict = OrderedDict()
        self.lock = threading.RLock()
        
        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        
        logger.info(f"📦 Response cache initialized (max_size={max_size}, ttl={default_ttl}s)")
    
    def _make_key(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a cache key from query and context
        
        Args:
            query: The user query
            context: Additional context (model, tools, etc.)
        
        Returns:
            Hash-based cache key
        """
        # Normalize query (lowercase, strip whitespace)
        normalized_query = query.lower().strip()
        
        # Create context string
        context_str = ""
        if context:
            # Sort keys for consistent hashing
            sorted_context = {k: context[k] for k in sorted(context.keys())}
            context_str = json.dumps(sorted_context, sort_keys=True)
        
        # Combine and hash
        combined = f"{normalized_query}|{context_str}"
        key = hashlib.md5(combined.encode()).hexdigest()
        
        return key
    
    def get(self, query: str, context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Get cached response
        
        Args:
            query: The user query
            context: Additional context
        
        Returns:
            Cached response or None if not found/expired
        """
        key = self._make_key(query, context)
        
        with self.lock:
            if key not in self.cache:
                self.misses += 1
                return None
            
            # Get cached item
            cached_item = self.cache[key]
            expiry_time = cached_item['expiry']
            
            # Check if expired
            if time.time() > expiry_time:
                # Expired - remove it
                del self.cache[key]
                self.misses += 1
                logger.debug(f"⏰ Cache expired for query: {query[:50]}...")
                return None
            
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            self.hits += 1
            
            logger.debug(f"✅ Cache HIT for query: {query[:50]}...")
            return cached_item['response']
    
    def set(self, query: str, response: Dict[str, Any], context: Optional[Dict[str, Any]] = None, ttl: Optional[int] = None):
        """
        Cache a response
        
        Args:
            query: The user query
            response: The response to cache
            context: Additional context
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        key = self._make_key(query, context)
        ttl = ttl or self.default_ttl
        
        with self.lock:
            # Check if we need to evict
            if len(self.cache) >= self.max_size and key not in self.cache:
                # Remove least recently used (first item)
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                self.evictions += 1
                logger.debug(f"🗑️ Cache evicted LRU item (size limit reached)")
            
            # Add/update cache
            self.cache[key] = {
                'response': response,
                'expiry': time.time() + ttl,
                'created': time.time()
            }
            
            # Move to end
            self.cache.move_to_end(key)
            
            logger.debug(f"💾 Cached response for query: {query[:50]}... (ttl={ttl}s)")
    
    def invalidate(self, query: str, context: Optional[Dict[str, Any]] = None):
        """
        Remove a specific cached item
        
        Args:
            query: The user query
            context: Additional context
        """
        key = self._make_key(query, context)
        
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                logger.debug(f"🗑️ Invalidated cache for query: {query[:50]}...")
    
    def clear(self):
        """Clear all cached items"""
        with self.lock:
            self.cache.clear()
            logger.info("🧹 Cache cleared")
    
    def cleanup_expired(self):
        """Remove all expired items"""
        with self.lock:
            current_time = time.time()
            expired_keys = [
                key for key, item in self.cache.items()
                if current_time > item['expiry']
            ]
            
            for key in expired_keys:
                del self.cache[key]
            
            if expired_keys:
                logger.info(f"🧹 Cleaned up {len(expired_keys)} expired cache items")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics
        
        Returns:
            Dictionary with cache statistics
        """
        with self.lock:
            total_requests = self.hits + self.misses
            hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'hits': self.hits,
                'misses': self.misses,
                'total_requests': total_requests,
                'hit_rate': round(hit_rate, 2),
                'evictions': self.evictions,
                'utilization': round(len(self.cache) / self.max_size * 100, 2)
            }
    
    def get_info(self) -> str:
        """Get formatted cache information"""
        stats = self.get_stats()
        return (
            f"📊 Cache Stats:\n"
            f"  Size: {stats['size']}/{stats['max_size']} ({stats['utilization']}%)\n"
            f"  Hits: {stats['hits']} | Misses: {stats['misses']}\n"
            f"  Hit Rate: {stats['hit_rate']}%\n"
            f"  Evictions: {stats['evictions']}"
        )


# Global cache instance
response_cache = ResponseCache(max_size=1000, default_ttl=3600)


def start_cache_cleanup_thread():
    """Start background thread to periodically clean up expired items"""
    def cleanup_loop():
        while True:
            time.sleep(300)  # Every 5 minutes
            try:
                response_cache.cleanup_expired()
            except Exception as e:
                logger.error(f"Error in cache cleanup: {e}")
    
    thread = threading.Thread(target=cleanup_loop, daemon=True)
    thread.start()
    logger.info("🧹 Cache cleanup thread started")


if __name__ == "__main__":
    # Test the cache
    logging.basicConfig(level=logging.DEBUG)
    
    cache = ResponseCache(max_size=3, default_ttl=5)
    
    # Test basic operations
    print("\n1. Testing cache set/get:")
    cache.set("What is Python?", {"answer": "A programming language"})
    result = cache.get("What is Python?")
    print(f"   Result: {result}")
    
    print("\n2. Testing case insensitivity:")
    result = cache.get("WHAT IS PYTHON?")
    print(f"   Result: {result}")
    
    print("\n3. Testing cache miss:")
    result = cache.get("What is Java?")
    print(f"   Result: {result}")
    
    print("\n4. Testing LRU eviction:")
    cache.set("Query 1", {"data": "1"})
    cache.set("Query 2", {"data": "2"})
    cache.set("Query 3", {"data": "3"})
    cache.set("Query 4", {"data": "4"})  # Should evict "What is Python?"
    print(f"   Cache size: {len(cache.cache)}")
    result = cache.get("What is Python?")
    print(f"   Old query result: {result}")
    
    print("\n5. Testing TTL expiration:")
    print("   Waiting 6 seconds...")
    time.sleep(6)
    result = cache.get("Query 2")
    print(f"   Expired result: {result}")
    
    print("\n6. Cache statistics:")
    print(f"   {cache.get_info()}")
