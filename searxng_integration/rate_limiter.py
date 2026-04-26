"""Token bucket rate limiter with jitter for anti-detection."""

import asyncio
import random
import time
from typing import Dict, Optional


class TokenBucket:
    """Token bucket for rate limiting."""
    
    def __init__(self, rate: float, capacity: int):
        """Initialize token bucket.
        
        Args:
            rate: Tokens per second (float for sub-second rates)
            capacity: Maximum burst capacity
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens from the bucket.
        
        Args:
            tokens: Number of tokens to acquire (default 1)
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens < tokens:
                wait_time = (tokens - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= tokens


class RateLimiter:
    """Rate limiter with per-instance token buckets and jitter."""
    
    def __init__(
        self,
        requests_per_second: float = 0.33,  # ~1 request per 3 seconds
        burst: int = 3,
        jitter_max: float = 2.0,
    ):
        """Initialize rate limiter.
        
        Args:
            requests_per_second: Maximum sustained request rate
            burst: Maximum burst capacity
            jitter_max: Maximum jitter in seconds
        """
        self.requests_per_second = requests_per_second
        self.burst = burst
        self.jitter_max = jitter_max
        self._buckets: Dict[str, TokenBucket] = {}
        self._global_bucket: Optional[TokenBucket] = None
    
    def _get_bucket(self, instance_id: str) -> TokenBucket:
        """Get or create token bucket for an instance."""
        if instance_id not in self._buckets:
            self._buckets[instance_id] = TokenBucket(
                rate=self.requests_per_second,
                capacity=self.burst,
            )
        return self._buckets[instance_id]
    
    async def acquire(self, instance_id: str) -> None:
        """Acquire permission to make a request.
        
        Waits for rate limit and adds jitter.
        
        Args:
            instance_id: Instance identifier for per-instance limiting
        """
        bucket = self._get_bucket(instance_id)
        await bucket.acquire()
        
        # Add random jitter
        if self.jitter_max > 0:
            jitter = random.uniform(0, self.jitter_max)
            await asyncio.sleep(jitter)
    
    async def acquire_global(self) -> None:
        """Acquire permission from global rate limiter."""
        if self._global_bucket is None:
            self._global_bucket = TokenBucket(
                rate=self.requests_per_second * 0.5,  # 50% of per-instance rate
                capacity=max(1, self.burst // 2),
            )
        await self._global_bucket.acquire()
    
    def reset_instance(self, instance_id: str) -> None:
        """Reset rate limiter for an instance."""
        if instance_id in self._buckets:
            del self._buckets[instance_id]
    
    def get_status(self) -> Dict[str, dict]:
        """Get current rate limiter status."""
        return {
            instance_id: {
                "tokens": bucket.tokens,
                "capacity": bucket.capacity,
                "rate": bucket.rate,
            }
            for instance_id, bucket in self._buckets.items()
        }
