"""SearXNG client with anti-detection and smart fallback."""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from anti_detect import AntiDetect
from cache_manager import CacheManager
from config import get_config
from instance_pool import InstancePool, NoHealthyInstance
from rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class SearXNGError(Exception):
    """Base exception for SearXNG client errors."""
    pass


class RateLimitedError(SearXNGError):
    """Raised when rate limited by an instance."""
    pass


class ServiceUnavailableError(SearXNGError):
    """Raised when service is unavailable."""
    pass


class SearXNGClient:
    """Client for SearXNG with anti-detection capabilities."""
    
    def __init__(self, config=None):
        """Initialize SearXNG client.
        
        Args:
            config: Optional SearXNGConfig instance
        """
        self.config = config or get_config()
        self.pool = InstancePool()
        self.limiter = RateLimiter(
            requests_per_second=1.0 / self.config.request_interval,
            burst=self.config.burst,
            jitter_max=self.config.jitter_max,
        )
        self.cache = CacheManager(
            max_size=self.config.cache_max_size,
            default_ttl=self.config.cache_ttl,
        )
        self.anti_detect = AntiDetect(enabled=self.config.user_agent_rotation)
        
        # Daily request tracking
        self._daily_requests = 0
        self._daily_reset_time = time.time() + 86400
        
        # HTTP client
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=self.config.connect_timeout,
                    read=self.config.timeout,
                ),
                follow_redirects=True,
                http2=True,
            )
        return self._client
    
    async def start(self) -> None:
        """Start the client."""
        await self.pool.start()
        logger.info("SearXNG client started")
    
    async def stop(self) -> None:
        """Stop the client."""
        await self.pool.stop()
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        logger.info("SearXNG client stopped")
    
    def _check_daily_limit(self) -> None:
        """Check if daily limit is exceeded."""
        now = time.time()
        
        # Reset daily counter
        if now > self._daily_reset_time:
            self._daily_requests = 0
            self._daily_reset_time = now + 86400
        
        if self._daily_requests >= self.config.daily_limit:
            raise SearXNGError(
                f"Daily request limit exceeded ({self.config.daily_limit}). "
                "Please try again tomorrow."
            )
    
    async def search(
        self,
        query: str,
        limit: int = 5,
        categories: Optional[List[str]] = None,
        language: str = "en-US",
        time_range: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search using SearXNG.
        
        Args:
            query: Search query
            limit: Maximum number of results
            categories: Search categories (e.g., ['general', 'news'])
            language: Language code
            time_range: Time range filter (day, week, month, year)
            
        Returns:
            Normalized search results
        """
        # Check daily limit
        self._check_daily_limit()
        
        # Check cache
        if self.config.cache_enabled:
            cached = self.cache.get(query, limit=limit, categories=categories, language=language)
            if cached:
                logger.info(f"Cache hit for query: {query}")
                return cached
        
        # Increment daily counter
        self._daily_requests += 1
        
        # Try with retries
        last_error = None
        for attempt in range(self.config.max_retries):
            instance = None
            try:
                # Get healthy instance
                instance = self.pool.get_healthy_instance()
                
                # Wait for rate limit
                await self.limiter.acquire(instance)
                
                # Build request
                params = {
                    "q": query,
                    "format": "json",
                    "language": language,
                }
                
                if categories:
                    params["categories"] = ",".join(categories)
                
                if time_range:
                    params["time_range"] = time_range
                
                # Get headers with anti-detection
                headers = self.anti_detect.get_headers({
                    "Accept": "application/json",
                })
                
                # Make request
                logger.info(f"Search attempt {attempt + 1}/{self.config.max_retries}: {query} via {instance}")
                
                client = await self._get_client()
                response = await client.get(
                    f"{instance}/search",
                    params=params,
                    headers=headers,
                )
                
                # Handle response
                if response.status_code == 429:
                    logger.warning(f"Rate limited by {instance}")
                    self.pool.cooldown(instance)
                    raise RateLimitedError(f"Rate limited by {instance}")
                
                if response.status_code >= 500:
                    logger.warning(f"Service unavailable: {instance} (status {response.status_code})")
                    self.pool.mark_unhealthy(instance)
                    raise ServiceUnavailableError(f"Service unavailable: {response.status_code}")
                
                response.raise_for_status()
                
                # Parse and normalize results
                data = response.json()
                results = self._normalize_results(data, limit)
                
                # Mark instance as healthy
                self.pool.mark_healthy(instance)
                
                # Cache results
                if self.config.cache_enabled:
                    self.cache.set(query, results, limit=limit, categories=categories, language=language)
                
                return results
                
            except (RateLimitedError, ServiceUnavailableError) as e:
                last_error = e
                continue
                
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP error from {instance}: {e.response.status_code}")
                if e.response.status_code == 403:
                    # Forbidden - remove instance
                    if instance:
                        self.pool.remove_instance(instance)
                elif e.response.status_code >= 500:
                    if instance:
                        self.pool.mark_unhealthy(instance)
                last_error = e
                
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                logger.warning(f"Connection error with {instance}: {e}")
                if instance:
                    self.pool.mark_unhealthy(instance)
                last_error = e
                
            except NoHealthyInstance:
                logger.error("No healthy instances available")
                raise SearXNGError("No healthy SearXNG instances available. Please try again later.")
                
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                last_error = e
            
            # Wait before retry with exponential backoff
            if attempt < self.config.max_retries - 1:
                delay = self.config.retry_delay * (2 ** attempt)
                logger.info(f"Retrying in {delay}s...")
                await asyncio.sleep(delay)
        
        # All retries exhausted
        raise SearXNGError(f"Search failed after {self.config.max_retries} attempts: {last_error}")
    
    def _normalize_results(self, data: Dict, limit: int) -> Dict[str, Any]:
        """Normalize SearXNG response to standard format.
        
        Args:
            data: Raw SearXNG response
            limit: Maximum number of results
            
        Returns:
            Normalized results
        """
        results = []
        
        # SearXNG returns results in 'results' key
        raw_results = data.get("results", [])
        
        for i, result in enumerate(raw_results[:limit]):
            normalized = {
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "description": result.get("content", ""),
                "position": i + 1,
            }
            
            # Add extra metadata if available
            if "publishedDate" in result:
                normalized["published_date"] = result["publishedDate"]
            if "engine" in result:
                normalized["engine"] = result["engine"]
            if "score" in result:
                normalized["score"] = result["score"]
            
            results.append(normalized)
        
        return {
            "success": True,
            "data": {
                "web": results,
                "query": data.get("query", ""),
                "total_results": len(raw_results),
                "returned_results": len(results),
            }
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        return {
            "daily_requests": self._daily_requests,
            "daily_limit": self.config.daily_limit,
            "daily_reset": self._daily_reset_time,
            "cache": self.cache.get_stats(),
            "pool": self.pool.get_status(),
            "rate_limiter": self.limiter.get_status(),
        }
    
    def reset_daily_counter(self) -> None:
        """Reset daily request counter."""
        self._daily_requests = 0
        self._daily_reset_time = time.time() + 86400


# Singleton instance
_client = None


async def get_client() -> SearXNGClient:
    """Get or create global client instance."""
    global _client
    if _client is None:
        _client = SearXNGClient()
        await _client.start()
    return _client


async def close_client() -> None:
    """Close global client instance."""
    global _client
    if _client:
        await _client.stop()
        _client = None
