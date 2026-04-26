"""Cache manager for search results."""

import hashlib
import json
import time
from typing import Any, Dict, Optional


class CacheManager:
    """In-memory cache with TTL support."""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """Initialize cache manager.
        
        Args:
            max_size: Maximum number of cached items
            default_ttl: Default time-to-live in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._access_count = 0
        self._hit_count = 0
    
    def _make_key(self, query: str, **params) -> str:
        """Create cache key from query and parameters."""
        key_data = json.dumps({"query": query.lower().strip(), **params}, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, query: str, **params) -> Optional[Any]:
        """Get cached result if available and not expired.
        
        Args:
            query: Search query
            **params: Additional parameters that affect caching
            
        Returns:
            Cached result or None
        """
        self._access_count += 1
        key = self._make_key(query, **params)
        
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        if time.time() > entry["expires"]:
            del self._cache[key]
            return None
        
        self._hit_count += 1
        return entry["data"]
    
    def set(self, query: str, data: Any, ttl: Optional[int] = None, **params) -> None:
        """Cache a result.
        
        Args:
            query: Search query
            data: Result data to cache
            ttl: Time-to-live in seconds (uses default if not specified)
            **params: Additional parameters that affect caching
        """
        # Evict oldest entries if cache is full
        if len(self._cache) >= self.max_size:
            self._evict_oldest()
        
        key = self._make_key(query, **params)
        self._cache[key] = {
            "data": data,
            "expires": time.time() + (ttl or self.default_ttl),
            "created": time.time(),
        }
    
    def _evict_oldest(self, count: int = 100) -> None:
        """Evict oldest entries from cache."""
        sorted_items = sorted(
            self._cache.items(),
            key=lambda x: x[1]["created"]
        )
        for key, _ in sorted_items[:count]:
            del self._cache[key]
    
    def invalidate(self, query: str, **params) -> bool:
        """Invalidate a cached entry.
        
        Returns:
            True if entry was found and removed
        """
        key = self._make_key(query, **params)
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._access_count
        hits = self._hit_count
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": hits,
            "misses": total - hits,
            "hit_rate": hits / total if total > 0 else 0.0,
            "total_requests": total,
        }
    
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count removed."""
        now = time.time()
        expired = [
            key for key, entry in self._cache.items()
            if now > entry["expires"]
        ]
        for key in expired:
            del self._cache[key]
        return len(expired)
