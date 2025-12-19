"""
Cache Optimizer - Phase 5: Optimization

Multi-level caching strategy with intelligent cache warming and invalidation.
"""

import time
import hashlib
import json
import logging
from typing import Any, Dict, Optional, Callable, List, Tuple
from functools import wraps
from dataclasses import dataclass, field
from collections import OrderedDict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    created_at: float
    last_accessed: float
    access_count: int = 0
    size_bytes: int = 0
    ttl: Optional[float] = None
    
    def is_expired(self) -> bool:
        """Check if entry has expired"""
        if self.ttl is None:
            return False
        return (time.time() - self.created_at) > self.ttl
    
    def touch(self):
        """Update last accessed time and increment counter"""
        self.last_accessed = time.time()
        self.access_count += 1


class LRUCache:
    """
    Least Recently Used (LRU) Cache
    
    Features:
    - Size-based eviction
    - TTL support
    - Access tracking
    - Hit/miss statistics
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: Optional[float] = None):
        """
        Initialize LRU cache
        
        Args:
            max_size: Maximum number of entries
            default_ttl: Default time-to-live in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        
        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        if key not in self.cache:
            self.misses += 1
            return None
        
        entry = self.cache[key]
        
        # Check expiration
        if entry.is_expired():
            self.delete(key)
            self.misses += 1
            return None
        
        # Update access time (LRU)
        entry.touch()
        self.cache.move_to_end(key)
        
        self.hits += 1
        return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """
        Set value in cache
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (overrides default)
        """
        # Use default TTL if not specified
        if ttl is None:
            ttl = self.default_ttl
        
        # Calculate size (rough estimate)
        try:
            size_bytes = len(json.dumps(value).encode())
        except:
            size_bytes = 0
        
        # Create entry
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=time.time(),
            last_accessed=time.time(),
            access_count=1,
            size_bytes=size_bytes,
            ttl=ttl
        )
        
        # Update existing or add new
        if key in self.cache:
            self.cache[key] = entry
            self.cache.move_to_end(key)
        else:
            self.cache[key] = entry
            
            # Evict if over size limit
            if len(self.cache) > self.max_size:
                self._evict_lru()
    
    def delete(self, key: str):
        """Delete entry from cache"""
        if key in self.cache:
            del self.cache[key]
    
    def clear(self):
        """Clear all entries"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
        self.evictions = 0
    
    def _evict_lru(self):
        """Evict least recently used entry"""
        if self.cache:
            self.cache.popitem(last=False)
            self.evictions += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        total_size = sum(entry.size_bytes for entry in self.cache.values())
        
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'hits': self.hits,
            'misses': self.misses,
            'evictions': self.evictions,
            'hit_rate': hit_rate,
            'total_size_bytes': total_size,
            'total_size_mb': total_size / (1024 * 1024)
        }
    
    def get_hot_keys(self, n: int = 10) -> List[Tuple[str, int]]:
        """Get most frequently accessed keys"""
        entries = [(k, v.access_count) for k, v in self.cache.items()]
        entries.sort(key=lambda x: x[1], reverse=True)
        return entries[:n]


class TieredCache:
    """
    Multi-tiered caching system
    
    Tiers:
    - L1: Fast in-memory cache (small, hot data)
    - L2: Larger in-memory cache (warm data)
    - L3: Optional persistent cache (cold data)
    """
    
    def __init__(
        self,
        l1_size: int = 100,
        l2_size: int = 1000,
        l1_ttl: float = 60,  # 1 minute
        l2_ttl: float = 600,  # 10 minutes
    ):
        """Initialize tiered cache"""
        self.l1 = LRUCache(max_size=l1_size, default_ttl=l1_ttl)
        self.l2 = LRUCache(max_size=l2_size, default_ttl=l2_ttl)
        
        # Statistics
        self.l1_promotions = 0
        self.l2_promotions = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache (checks L1 then L2)"""
        # Check L1
        value = self.l1.get(key)
        if value is not None:
            return value
        
        # Check L2
        value = self.l2.get(key)
        if value is not None:
            # Promote to L1
            self.l1.set(key, value)
            self.l1_promotions += 1
            return value
        
        return None
    
    def set(self, key: str, value: Any, tier: int = 1):
        """
        Set value in cache
        
        Args:
            key: Cache key
            value: Value to cache
            tier: Which tier to cache in (1 or 2)
        """
        if tier == 1:
            self.l1.set(key, value)
        else:
            self.l2.set(key, value)
    
    def delete(self, key: str):
        """Delete from all tiers"""
        self.l1.delete(key)
        self.l2.delete(key)
    
    def clear(self):
        """Clear all tiers"""
        self.l1.clear()
        self.l2.clear()
        self.l1_promotions = 0
        self.l2_promotions = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all tiers"""
        return {
            'l1': self.l1.get_stats(),
            'l2': self.l2.get_stats(),
            'l1_promotions': self.l1_promotions,
            'l2_promotions': self.l2_promotions
        }


class CacheOptimizer:
    """
    Cache optimization with intelligent strategies
    
    Features:
    - Tiered caching (L1/L2)
    - Cache warming
    - Intelligent invalidation
    - Performance monitoring
    """
    
    def __init__(
        self,
        l1_size: int = 100,
        l2_size: int = 1000,
        l1_ttl: float = 60,
        l2_ttl: float = 600
    ):
        """Initialize cache optimizer"""
        self.cache = TieredCache(
            l1_size=l1_size,
            l2_size=l2_size,
            l1_ttl=l1_ttl,
            l2_ttl=l2_ttl
        )
        
        # Warm-up queue
        self.warmup_keys: List[Tuple[str, Callable]] = []
    
    def cached(
        self,
        ttl: Optional[float] = None,
        tier: int = 1,
        key_func: Optional[Callable] = None
    ):
        """
        Decorator for caching function results
        
        Args:
            ttl: Time-to-live in seconds
            tier: Cache tier (1 or 2)
            key_func: Custom function to generate cache key
        
        Example:
            @cache_optimizer.cached(ttl=60, tier=1)
            def expensive_operation(x, y):
                return x + y
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = self._generate_key(func.__name__, args, kwargs)
                
                # Try to get from cache
                cached_value = self.cache.get(cache_key)
                if cached_value is not None:
                    return cached_value
                
                # Compute value
                value = func(*args, **kwargs)
                
                # Store in cache
                self.cache.set(cache_key, value, tier=tier)
                
                return value
            
            return wrapper
        return decorator
    
    def _generate_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Generate cache key from function name and arguments"""
        key_data = {
            'func': func_name,
            'args': args,
            'kwargs': kwargs
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def register_warmup(self, key: str, loader: Callable):
        """
        Register a key for cache warming
        
        Args:
            key: Cache key
            loader: Function to load the value
        """
        self.warmup_keys.append((key, loader))
    
    def warm_cache(self):
        """Warm cache by loading registered keys"""
        logger.info(f"Warming cache with {len(self.warmup_keys)} keys...")
        
        start_time = time.time()
        loaded = 0
        
        for key, loader in self.warmup_keys:
            try:
                value = loader()
                self.cache.set(key, value, tier=2)  # Store in L2
                loaded += 1
            except Exception as e:
                logger.error(f"Failed to warm key '{key}': {e}")
        
        elapsed = time.time() - start_time
        logger.info(f"Cache warmed: {loaded}/{len(self.warmup_keys)} keys in {elapsed:.2f}s")
    
    def invalidate_pattern(self, pattern: str):
        """
        Invalidate all keys matching a pattern
        
        Args:
            pattern: Key pattern (supports wildcards)
        """
        # Simple pattern matching
        keys_to_delete = []
        
        for key in self.cache.l1.cache.keys():
            if pattern in key:
                keys_to_delete.append(key)
        
        for key in self.cache.l2.cache.keys():
            if pattern in key:
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            self.cache.delete(key)
        
        logger.info(f"Invalidated {len(keys_to_delete)} keys matching '{pattern}'")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        return self.cache.get_stats()
    
    def get_hot_keys(self, tier: int = 1, n: int = 10) -> List[Tuple[str, int]]:
        """Get most frequently accessed keys from a tier"""
        if tier == 1:
            return self.cache.l1.get_hot_keys(n)
        else:
            return self.cache.l2.get_hot_keys(n)


# Global cache optimizer instance
cache_optimizer = CacheOptimizer(
    l1_size=100,   # 100 hot items
    l2_size=1000,  # 1000 warm items
    l1_ttl=60,     # 1 minute L1 TTL
    l2_ttl=600     # 10 minutes L2 TTL
)
