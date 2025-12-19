"""
Memory-Efficient Cache Manager
LRU cache with size limits for laptop optimization
Max 50MB RAM usage
"""

import hashlib
import time
import sys
import logging
from collections import OrderedDict

logger = logging.getLogger(__name__)

class MemoryEfficientCache:
    """Lightweight LRU cache with memory constraints"""
    
    def __init__(self, max_size_mb=50, ttl=1800):
        """
        Initialize cache
        
        Args:
            max_size_mb: Maximum cache size in megabytes
            ttl: Time-to-live in seconds (default 30 minutes)
        """
        self.cache = OrderedDict()
        self.max_size = max_size_mb * 1024 * 1024  # Convert to bytes
        self.current_size = 0
        self.ttl = ttl
        
        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        
        logger.info(f"💾 Cache initialized: {max_size_mb}MB max, {ttl}s TTL")
    
    def _get_size(self, obj) -> int:
        """Estimate object size in bytes"""
        return sys.getsizeof(str(obj))
    
    def _get_key(self, query: str) -> str:
        """Generate short hash key"""
        return hashlib.md5(query.lower().strip().encode()).hexdigest()[:16]
    
    def get(self, query: str):
        """
        Retrieve cached result
        
        Args:
            query: Query string to look up
            
        Returns:
            Cached data or None
        """
        key = self._get_key(query)
        
        if key in self.cache:
            data, timestamp, size = self.cache[key]
            
            # Check if expired
            if time.time() - timestamp < self.ttl:
                # Move to end (LRU)
                self.cache.move_to_end(key)
                self.hits += 1
                logger.debug(f"✅ Cache hit: {query[:30]}...")
                return data
            else:
                # Expired, remove
                self.current_size -= size
                del self.cache[key]
                logger.debug(f"⏰ Expired: {query[:30]}...")
        
        self.misses += 1
        return None
    
    def set(self, query: str, data):
        """
        Store result in cache
        
        Args:
            query: Query string as key
            data: Result to cache
        """
        key = self._get_key(query)
        size = self._get_size(data)
        
        # Skip if single item is too large
        if size > self.max_size * 0.1:  # Max 10% per item
            logger.warning(f"⚠️ Item too large to cache: {size / 1024:.1f}KB")
            return
        
        # Evict oldest entries if needed
        while self.current_size + size > self.max_size and self.cache:
            old_key, (_, _, old_size) = self.cache.popitem(last=False)
            self.current_size -= old_size
            self.evictions += 1
        
        # Store new entry
        self.cache[key] = (data, time.time(), size)
        self.cache.move_to_end(key)
        self.current_size += size
        
        logger.debug(f"💾 Cached: {query[:30]}... ({size / 1024:.1f}KB)")
    
    def clear_expired(self):
        """Remove all expired entries"""
        now = time.time()
        expired_keys = [
            k for k, (_, ts, _) in self.cache.items() 
            if now - ts > self.ttl
        ]
        
        for key in expired_keys:
            _, _, size = self.cache[key]
            self.current_size -= size
            del self.cache[key]
        
        if expired_keys:
            logger.info(f"🧹 Cleared {len(expired_keys)} expired entries")
    
    def clear(self):
        """Clear entire cache"""
        self.cache.clear()
        self.current_size = 0
        logger.info("🗑️ Cache cleared")
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'entries': len(self.cache),
            'size_mb': round(self.current_size / (1024 * 1024), 2),
            'max_size_mb': round(self.max_size / (1024 * 1024), 2),
            'hit_rate': f"{hit_rate:.1f}%",
            'hits': self.hits,
            'misses': self.misses,
            'evictions': self.evictions,
            'total_requests': total_requests
        }
