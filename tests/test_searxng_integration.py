"""Tests for SearXNG integration."""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from searxng_integration.anti_detect import AntiDetect
from searxng_integration.cache_manager import CacheManager
from searxng_integration.config import SearXNGConfig
from searxng_integration.instance_pool import InstancePool, InstanceStatus, NoHealthyInstance
from searxng_integration.rate_limiter import RateLimiter, TokenBucket
from searxng_integration.searxng_client import SearXNGClient, SearXNGError


class TestAntiDetect:
    """Test anti-detection utilities."""
    
    def test_get_headers(self):
        """Test header generation."""
        anti = AntiDetect(enabled=True)
        headers = anti.get_headers()
        
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "Accept-Language" in headers
        assert "Accept-Encoding" in headers
        assert headers["User-Agent"] in AntiDetect.USER_AGENTS
    
    def test_get_headers_disabled(self):
        """Test disabled anti-detection."""
        anti = AntiDetect(enabled=False)
        headers = anti.get_headers()
        assert headers == {}
    
    def test_get_headers_with_extra(self):
        """Test headers with extra fields."""
        anti = AntiDetect(enabled=True)
        headers = anti.get_headers({"X-Custom": "value"})
        assert headers["X-Custom"] == "value"
    
    def test_user_agent_rotation(self):
        """Test User-Agent rotation."""
        anti = AntiDetect(enabled=True)
        uas = set()
        for _ in range(20):
            headers = anti.get_headers()
            uas.add(headers["User-Agent"])
        assert len(uas) > 1  # Should rotate


class TestCacheManager:
    """Test cache manager."""
    
    def test_basic_cache(self):
        """Test basic cache operations."""
        cache = CacheManager()
        
        # Test set and get
        cache.set("query1", {"results": [1, 2, 3]})
        result = cache.get("query1")
        assert result == {"results": [1, 2, 3]}
    
    def test_cache_ttl(self):
        """Test cache TTL expiration."""
        cache = CacheManager(default_ttl=0)
        cache.set("query1", {"results": [1]})
        time.sleep(0.1)
        result = cache.get("query1")
        assert result is None
    
    def test_cache_invalidation(self):
        """Test cache invalidation."""
        cache = CacheManager()
        cache.set("query1", {"results": [1]})
        cache.invalidate("query1")
        result = cache.get("query1")
        assert result is None
    
    def test_cache_stats(self):
        """Test cache statistics."""
        cache = CacheManager()
        cache.set("query1", {"results": [1]})
        cache.get("query1")
        cache.get("query1")
        cache.get("query2")  # Miss
        
        stats = cache.get_stats()
        assert stats["size"] == 2
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 2/3


class TestRateLimiter:
    """Test rate limiter."""
    
    @pytest.mark.asyncio
    async def test_token_bucket(self):
        """Test token bucket."""
        bucket = TokenBucket(rate=10, capacity=5)
        
        # Should acquire immediately (has tokens)
        await bucket.acquire()
        assert bucket.tokens <= 4
    
    @pytest.mark.asyncio
    async def test_rate_limiter(self):
        """Test rate limiter with jitter."""
        limiter = RateLimiter(
            requests_per_second=10,
            burst=5,
            jitter_max=0.1,
        )
        
        start = time.time()
        await limiter.acquire("instance1")
        await limiter.acquire("instance1")
        elapsed = time.time() - start
        
        # Should be fast (within burst)
        assert elapsed < 1.0
    
    def test_status(self):
        """Test rate limiter status."""
        limiter = RateLimiter()
        status = limiter.get_status()
        assert isinstance(status, dict)


class TestInstancePool:
    """Test instance pool."""
    
    def test_initialization(self):
        """Test pool initialization."""
        pool = InstancePool(["https://instance1.com", "https://instance2.com"])
        assert len(pool.instances) == 2
    
    def test_get_healthy_instance(self):
        """Test getting healthy instance."""
        pool = InstancePool(["https://instance1.com"])
        url = pool.get_healthy_instance()
        assert url == "https://instance1.com"
    
    def test_no_healthy_instance(self):
        """Test no healthy instances."""
        pool = InstancePool()
        with pytest.raises(NoHealthyInstance):
            pool.get_healthy_instance()
    
    def test_mark_unhealthy(self):
        """Test marking instance unhealthy."""
        pool = InstancePool(["https://instance1.com"])
        pool.mark_unhealthy("https://instance1.com")
        
        inst = pool.instances["https://instance1.com"]
        assert not inst.is_healthy
        assert inst.failure_count == 1
    
    def test_cooldown(self):
        """Test instance cooldown."""
        pool = InstancePool(["https://instance1.com"])
        pool.cooldown("https://instance1.com", duration=60)
        
        inst = pool.instances["https://instance1.com"]
        assert inst.is_in_cooldown()
    
    def test_add_remove_instance(self):
        """Test adding and removing instances."""
        pool = InstancePool()
        pool.add_instance("https://new.com")
        assert "https://new.com" in pool.instances
        
        pool.remove_instance("https://new.com")
        assert "https://new.com" not in pool.instances
    
    def test_get_status(self):
        """Test pool status."""
        pool = InstancePool(["https://instance1.com"])
        status = pool.get_status()
        assert status["total"] == 1
        assert status["healthy"] == 1


class TestSearXNGConfig:
    """Test configuration."""
    
    def test_default_config(self):
        """Test default configuration."""
        config = SearXNGConfig()
        assert config.request_interval == 3.0
        assert config.burst == 3
        assert config.daily_limit == 500
    
    def test_from_dict(self):
        """Test creating config from dict."""
        config = SearXNGConfig.from_dict({
            "request_interval": 5.0,
            "daily_limit": 1000,
        })
        assert config.request_interval == 5.0
        assert config.daily_limit == 1000
    
    def test_custom_instances(self):
        """Test custom instances from env."""
        import os
        os.environ["SEARXNG_INSTANCES"] = "https://custom1.com,https://custom2.com"
        config = SearXNGConfig()
        assert config.instances == ["https://custom1.com", "https://custom2.com"]
        del os.environ["SEARXNG_INSTANCES"]


class TestSearXNGClient:
    """Test SearXNG client."""
    
    @pytest.mark.asyncio
    async def test_search_success(self):
        """Test successful search."""
        client = SearXNGClient()
        
        # Mock the pool and HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "query": "test",
            "results": [
                {"title": "Result 1", "url": "https://example.com/1", "content": "Description 1"},
                {"title": "Result 2", "url": "https://example.com/2", "content": "Description 2"},
            ]
        }
        
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        client._client = mock_client
        
        # Mock pool
        client.pool.instances = {
            "https://instance1.com": InstanceStatus(url="https://instance1.com")
        }
        
        result = await client.search("test", limit=2)
        
        assert result["success"] is True
        assert len(result["data"]["web"]) == 2
        assert result["data"]["web"][0]["title"] == "Result 1"
    
    @pytest.mark.asyncio
    async def test_search_rate_limited(self):
        """Test rate limited response."""
        client = SearXNGClient()
        
        mock_response = MagicMock()
        mock_response.status_code = 429
        
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        client._client = mock_client
        
        client.pool.instances = {
            "https://instance1.com": InstanceStatus(url="https://instance1.com")
        }
        
        with pytest.raises(SearXNGError):
            await client.search("test")
    
    @pytest.mark.asyncio
    async def test_search_no_instances(self):
        """Test search with no instances."""
        client = SearXNGClient()
        client.pool.instances = {}
        
        with pytest.raises(SearXNGError):
            await client.search("test")
    
    def test_normalize_results(self):
        """Test result normalization."""
        client = SearXNGClient()
        
        raw_data = {
            "query": "test",
            "results": [
                {"title": "Title", "url": "https://example.com", "content": "Content"},
            ]
        }
        
        result = client._normalize_results(raw_data, 5)
        
        assert result["success"] is True
        assert result["data"]["web"][0]["title"] == "Title"
        assert result["data"]["web"][0]["position"] == 1
    
    def test_daily_limit(self):
        """Test daily limit enforcement."""
        client = SearXNGClient()
        client._daily_requests = 500
        
        with pytest.raises(SearXNGError):
            client._check_daily_limit()
    
    def test_get_stats(self):
        """Test client statistics."""
        client = SearXNGClient()
        stats = client.get_stats()
        
        assert "daily_requests" in stats
        assert "daily_limit" in stats
        assert "cache" in stats
        assert "pool" in stats


class TestIntegration:
    """Integration tests."""
    
    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test full search workflow."""
        from searxng_integration.searxng_tools import searxng_search_tool
        
        # This would require mocking the HTTP client
        # For now, just test the function exists and can be called
        assert callable(searxng_search_tool)
    
    def test_tool_error(self):
        """Test error response formatting."""
        from searxng_integration.searxng_tools import tool_error
        
        result = tool_error("Test error")
        data = json.loads(result)
        assert data["error"] == "Test error"
        assert data["success"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
