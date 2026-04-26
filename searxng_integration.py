#!/usr/bin/env python3
"""SearXNG integration for Hermes Agent.

Provides free web search using public SearXNG instances with anti-detection.
No API keys required.

Usage in Hermes Agent:
    /tool searxng_search query="Python best practices"
"""

import asyncio
import json
import logging
import random
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ─── Configuration ──────────────────────────────────────────────────────────

SEARXNG_INSTANCES = [
    "https://baresearch.org",
    "https://copp.gg",
    "https://etsi.me",
    "https://failsearx.culturanerd.it",
    "https://find.xenorio.xyz",
    "https://grep.vim.wtf",
    "https://kantan.cat",
    "https://o5.gg",
    "https://ooglester.com",
    "https://opnxng.com",
    "https://paulgo.io",
    "https://priv.au",
    "https://s.mble.dk",
    "https://search.2b9t.xyz",
    "https://search.abohiccups.com",
    "https://search.anoni.net",
    "https://search.bladerunn.in",
    "https://search.catboy.house",
    "https://search.charliewhiskey.net",
    "https://search.chocolatemoo53.com",
]

# Anti-detection settings
REQUEST_INTERVAL = 5.0  # seconds between requests (increased to avoid rate limits)
JITTER_MIN = 1.0
JITTER_MAX = 4.0
MAX_RETRIES = 5
TIMEOUT = 20
CACHE_TTL = 600  # 10 minutes cache

# User-Agent rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]

ACCEPT_LANGUAGES = [
    "zh-CN,zh;q=0.9,en;q=0.8",
    "en-US,en;q=0.9",
    "en-GB,en;q=0.8",
    "zh-TW,zh;q=0.9,en;q=0.8",
]


class AntiDetect:
    """Anti-detection header generator."""
    
    def __init__(self):
        self._ua_index = random.randint(0, len(USER_AGENTS) - 1)
    
    def get_headers(self) -> Dict[str, str]:
        """Generate realistic browser headers."""
        self._ua_index = (self._ua_index + random.randint(1, 3)) % len(USER_AGENTS)
        
        return {
            "User-Agent": USER_AGENTS[self._ua_index],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": random.choice(ACCEPT_LANGUAGES),
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0",
        }


class RateLimiter:
    """Simple rate limiter with jitter."""
    
    def __init__(self, min_interval: float = 5.0, jitter_min: float = 1.0, jitter_max: float = 4.0):
        self.min_interval = min_interval
        self.jitter_min = jitter_min
        self.jitter_max = jitter_max
        self._last_request: Dict[str, float] = {}
        self._global_last = 0.0
    
    async def acquire(self, instance: str):
        """Wait for rate limit with jitter."""
        now = time.time()
        
        # Global rate limit
        global_elapsed = now - self._global_last
        if global_elapsed < self.min_interval:
            wait = self.min_interval - global_elapsed
            logger.debug(f"Global rate limit: waiting {wait:.1f}s")
            await asyncio.sleep(wait)
        
        # Per-instance rate limit
        last = self._last_request.get(instance, 0)
        elapsed = time.time() - last
        if elapsed < self.min_interval:
            wait = self.min_interval - elapsed
            logger.debug(f"Instance rate limit: waiting {wait:.1f}s")
            await asyncio.sleep(wait)
        
        # Add jitter
        jitter = random.uniform(self.jitter_min, self.jitter_max)
        logger.debug(f"Adding jitter: {jitter:.1f}s")
        await asyncio.sleep(jitter)
        
        self._last_request[instance] = time.time()
        self._global_last = time.time()


class SearXNGClient:
    """SearXNG client with anti-detection and smart fallback."""
    
    def __init__(self):
        self.instances = SEARXNG_INSTANCES.copy()
        self._current = 0
        self._failed_instances: Dict[str, float] = {}
        self._cache: Dict[str, tuple[float, Any]] = {}
        self.anti_detect = AntiDetect()
        self.rate_limiter = RateLimiter(
            min_interval=REQUEST_INTERVAL,
            jitter_min=JITTER_MIN,
            jitter_max=JITTER_MAX,
        )
    
    def _get_next_instance(self) -> Optional[str]:
        """Get next available instance with health check."""
        now = time.time()
        
        # Clean up old failures
        self._failed_instances = {
            k: v for k, v in self._failed_instances.items()
            if now - v < 300  # 5 minute cooldown
        }
        
        # Try to find a healthy instance
        attempts = 0
        while attempts < len(self.instances):
            instance = self.instances[self._current]
            self._current = (self._current + 1) % len(self.instances)
            
            if instance not in self._failed_instances:
                return instance
            
            attempts += 1
        
        # All instances in cooldown, try anyway
        if self.instances:
            return random.choice(self.instances)
        return None
    
    def _mark_failed(self, instance: str):
        """Mark instance as failed."""
        self._failed_instances[instance] = time.time()
        logger.warning(f"Instance failed: {instance}")
    
    def _get_cached(self, key: str) -> Optional[Any]:
        """Get cached result."""
        if key in self._cache:
            timestamp, data = self._cache[key]
            if time.time() - timestamp < CACHE_TTL:
                logger.info("Cache hit!")
                return data
            del self._cache[key]
        return None
    
    def _set_cached(self, key: str, data: Any):
        """Cache result."""
        self._cache[key] = (time.time(), data)
    
    async def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Search with retries and anti-detection."""
        cache_key = f"{query}:{limit}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        last_error = None
        tried_instances = set()
        
        for attempt in range(MAX_RETRIES):
            instance = self._get_next_instance()
            if not instance:
                break
            
            if instance in tried_instances:
                continue
            tried_instances.add(instance)
            
            try:
                # Rate limiting
                await self.rate_limiter.acquire(instance)
                
                # Anti-detection headers
                headers = self.anti_detect.get_headers()
                
                logger.info(f"Searching via {instance} (attempt {attempt + 1})")
                
                async with httpx.AsyncClient(
                    timeout=TIMEOUT, 
                    follow_redirects=True,
                    headers=headers,
                ) as client:
                    # Step 1: Visit homepage to get cookies
                    logger.debug(f"Visiting homepage: {instance}")
                    home_resp = await client.get(instance)
                    if home_resp.status_code != 200:
                        logger.warning(f"Homepage failed: {home_resp.status_code}")
                        self._mark_failed(instance)
                        continue
                    
                    # Wait before search
                    await asyncio.sleep(random.uniform(2, 4))
                    
                    # Step 2: Perform search (HTML format to avoid JSON API restrictions)
                    search_url = f"{instance}/search"
                    params = {
                        "q": query,
                        "language": "zh-CN",
                        "safesearch": "0",
                    }
                    
                    response = await client.get(search_url, params=params)
                    
                    if response.status_code == 429:
                        logger.warning(f"Rate limited: {instance}")
                        self._mark_failed(instance)
                        continue
                    
                    if response.status_code == 403:
                        logger.warning(f"Forbidden: {instance}")
                        self._mark_failed(instance)
                        continue
                    
                    if response.status_code == 503:
                        logger.warning(f"Service unavailable: {instance}")
                        self._mark_failed(instance)
                        continue
                    
                    response.raise_for_status()
                    
                    # Parse HTML results
                    results = self._parse_html_results(response.text, limit)
                    
                    if results:
                        result = {
                            "success": True,
                            "data": {
                                "web": results,
                                "query": query,
                                "total_results": len(results),
                                "returned_results": len(results),
                            }
                        }
                        
                        self._set_cached(cache_key, result)
                        logger.info(f"Search successful: {len(results)} results")
                        return result
                    else:
                        logger.warning(f"No results found on {instance}")
                        
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP error on {instance}: {e.response.status_code}")
                self._mark_failed(instance)
                last_error = e
                
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                logger.warning(f"Connection error on {instance}: {e}")
                self._mark_failed(instance)
                last_error = e
                
            except Exception as e:
                logger.error(f"Unexpected error on {instance}: {e}")
                self._mark_failed(instance)
                last_error = e
            
            # Exponential backoff between retries
            if attempt < MAX_RETRIES - 1:
                backoff = min(2 ** attempt + random.uniform(1, 3), 30)
                logger.info(f"Retrying in {backoff:.1f}s...")
                await asyncio.sleep(backoff)
        
        return {
            "success": False,
            "error": f"Search failed after {len(tried_instances)} instances. Last error: {last_error}"
        }
    
    def _parse_html_results(self, html: str, limit: int) -> List[Dict[str, str]]:
        """Parse search results from HTML.
        
        SearXNG HTML structure:
        <article class="result">
            <h3><a href="URL">Title</a></h3>
            <p class="content">Description</p>
        </article>
        """
        import re
        
        results = []
        
        # Find all result articles
        # Pattern for SearXNG result items
        result_pattern = r'<article[^>]*class="[^"]*result[^"]*"[^>]*>.*?</article>'
        result_blocks = re.findall(result_pattern, html, re.DOTALL)
        
        for i, block in enumerate(result_blocks[:limit]):
            # Extract URL and title
            url_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
            if not url_match:
                continue
            
            url = url_match.group(1)
            title = re.sub(r'<[^>]+>', '', url_match.group(2)).strip()
            
            # Extract description
            desc_match = re.search(r'<p[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</p>', block, re.DOTALL)
            if desc_match:
                description = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()
            else:
                # Try alternative description patterns
                desc_match = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
                description = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip() if desc_match else ""
            
            # Clean up URL
            if url.startswith('/'):
                url = f"{self.instances[0]}{url}"
            
            results.append({
                "title": title,
                "url": url,
                "description": description,
                "position": i + 1,
            })
        
        return results


# Global client
_client = SearXNGClient()


# ─── Hermes Agent Integration ───────────────────────────────────────────────

try:
    from tools.registry import registry, tool_error
    
    async def searxng_search_handler(args: dict) -> str:
        """Handle searxng_search tool calls."""
        query = args.get("query", "").strip()
        if not query:
            return tool_error("Query cannot be empty")
        
        limit = max(1, min(20, int(args.get("limit", 5))))
        
        try:
            result = await _client.search(query, limit)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("SearXNG search error: %s", e)
            return tool_error(f"Search failed: {e}")
    
    SEARXNG_SEARCH_SCHEMA = {
        "name": "searxng_search",
        "description": (
            "免费搜索网页信息（基于 SearXNG 元搜索引擎）。"
            "无需 API Key，自动轮换多个公共实例，具有反爬保护。"
            "适合市场调研和日常搜索。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询词（支持中英文）"
                },
                "limit": {
                    "type": "integer",
                    "description": "返回结果数量（1-20，默认5）",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 20
                }
            },
            "required": ["query"]
        }
    }
    
    registry.register(
        name="searxng_search",
        toolset="searxng",
        schema=SEARXNG_SEARCH_SCHEMA,
        handler=searxng_search_handler,
        check_fn=lambda: True,
        requires_env=[],
        is_async=True,
        emoji="🔎",
        max_result_size_chars=100_000,
    )
    
    logger.info("✅ SearXNG tool registered with Hermes Agent")
    
except ImportError:
    logger.info("Running in standalone mode (Hermes Agent not available)")
    
    def tool_error(message, **extra):
        result = {"error": str(message), "success": False}
        if extra:
            result.update(extra)
        return json.dumps(result, ensure_ascii=False)


# ─── Standalone Test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    async def test():
        print("🔎 Testing SearXNG Search with Anti-Detection")
        print("=" * 60)
        
        queries = [
            "Python async programming",
            "AI market trends 2024",
        ]
        
        for query in queries:
            print(f"\n📋 Query: {query}")
            print("-" * 40)
            
            result = await _client.search(query, limit=3)
            
            if result.get("success"):
                print(f"✅ Success! Found {result['data']['total_results']} results")
                for item in result["data"]["web"]:
                    print(f"\n{item['position']}. {item['title']}")
                    print(f"   URL: {item['url']}")
                    print(f"   {item['description'][:120]}...")
            else:
                print(f"❌ Error: {result.get('error')}")
            
            # Wait between queries
            if query != queries[-1]:
                wait = random.uniform(5, 8)
                print(f"\n⏳ Waiting {wait:.1f}s before next query...")
                await asyncio.sleep(wait)
        
        print("\n" + "=" * 60)
        print("🏁 Test completed!")
    
    asyncio.run(test())
