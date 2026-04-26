"""SearXNG tool integration for Hermes Agent.

This module provides free web search capabilities using public SearXNG instances,
with built-in anti-detection, rate limiting, and intelligent caching.

Usage:
    # In Hermes Agent conversation:
    /tool searxng_search query="Python web scraping best practices"
    
    # Or let the agent use it automatically when web_search is unavailable
"""

import json
import logging
from typing import Dict, Any, Optional

from .searxng_client import SearXNGClient, get_client, close_client
from .config import get_config

logger = logging.getLogger(__name__)


async def searxng_search_tool(
    query: str,
    limit: int = 5,
    categories: Optional[str] = None,
    language: str = "zh-CN",
    time_range: Optional[str] = None,
) -> str:
    """Search the web using free SearXNG public instances.
    
    This tool provides free web search without requiring any API keys.
    It automatically manages multiple public SearXNG instances with:
    - Anti-detection headers and User-Agent rotation
    - Rate limiting and jitter to avoid being blocked
    - Intelligent caching for repeated queries
    - Automatic failover between instances
    - Daily request limits for self-protection
    
    Args:
        query: Search query (e.g., "2024 AI market trends")
        limit: Maximum number of results (1-20, default 5)
        categories: Search categories, comma-separated (e.g., "general,news")
        language: Language code (default "zh-CN" for Chinese)
        time_range: Time filter - "day", "week", "month", or "year"
    
    Returns:
        JSON string with search results:
        {
            "success": true,
            "data": {
                "web": [
                    {
                        "title": "Result title",
                        "url": "https://example.com",
                        "description": "Result description...",
                        "position": 1
                    }
                ],
                "query": "original query",
                "total_results": 100,
                "returned_results": 5
            }
        }
    
    Note:
        - No API key required
        - Results may vary slightly between calls due to instance rotation
        - Cached results are returned for identical queries within 5 minutes
        - Daily limit: 500 requests (configurable)
    """
    try:
        # Validate inputs
        if not query or not query.strip():
            return tool_error("Query cannot be empty")
        
        limit = max(1, min(20, int(limit)))
        
        # Parse categories
        cat_list = None
        if categories:
            cat_list = [c.strip() for c in categories.split(",")]
        
        # Get client and search
        client = await get_client()
        
        results = await client.search(
            query=query.strip(),
            limit=limit,
            categories=cat_list,
            language=language,
            time_range=time_range,
        )
        
        return json.dumps(results, indent=2, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"SearXNG search error: {e}")
        return tool_error(f"Search failed: {str(e)}")


def tool_error(message: str, **extra) -> str:
    """Return JSON error response."""
    result = {"error": str(message), "success": False}
    if extra:
        result.update(extra)
    return json.dumps(result, ensure_ascii=False)


# ─── Hermes Agent Registry Integration ──────────────────────────────────────

# Try to import Hermes registry for integration
try:
    import sys
    import os
    
    # Add hermes-agent tools directory to path if available
    hermes_tools_path = os.path.expanduser("~/.hermes/tools")
    if os.path.exists(hermes_tools_path):
        sys.path.insert(0, hermes_tools_path)
    
    # Try to import registry
    from tools.registry import registry, tool_error as registry_tool_error
    
    # Define tool schema for Hermes Agent
    SEARXNG_SEARCH_SCHEMA = {
        "name": "searxng_search",
        "description": (
            "免费搜索网页信息（基于 SearXNG 元搜索引擎）。"
            "适合市场调研、信息搜集等场景，无需 API Key。"
            "自动管理多个公共实例，具有反爬保护和智能缓存。"
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
                },
                "categories": {
                    "type": "string",
                    "description": "搜索类别，逗号分隔（如：general,news,images）",
                    "default": "general"
                },
                "language": {
                    "type": "string",
                    "description": "语言代码（默认 zh-CN）",
                    "default": "zh-CN"
                },
                "time_range": {
                    "type": "string",
                    "description": "时间范围过滤：day（今天）, week（本周）, month（本月）, year（今年）",
                    "enum": ["day", "week", "month", "year"]
                }
            },
            "required": ["query"]
        }
    }
    
    # Register the tool
    registry.register(
        name="searxng_search",
        toolset="searxng",
        schema=SEARXNG_SEARCH_SCHEMA,
        handler=lambda args, **kw: searxng_search_tool(
            query=args.get("query", ""),
            limit=args.get("limit", 5),
            categories=args.get("categories"),
            language=args.get("language", "zh-CN"),
            time_range=args.get("time_range"),
        ),
        check_fn=lambda: True,  # Always available (uses public instances)
        requires_env=[],  # No API keys needed!
        is_async=True,
        emoji="🔎",
        max_result_size_chars=100_000,
    )
    
    logger.info("SearXNG tool registered with Hermes Agent")
    
except ImportError:
    logger.info("Hermes Agent registry not available, running in standalone mode")
    registry = None


# ─── Standalone Testing ───────────────────────────────────────────────────

if __name__ == "__main__":
    import asyncio
    
    async def test():
        print("🔎 SearXNG Search Tool Test")
        print("=" * 50)
        
        # Test search
        query = "Python async programming best practices"
        print(f"\nSearching: {query}")
        
        result = await searxng_search_tool(query, limit=3)
        data = json.loads(result)
        
        if data.get("success"):
            print(f"✅ Success! Found {data['data']['total_results']} results")
            print(f"\nTop results:")
            for item in data["data"]["web"]:
                print(f"  {item['position']}. {item['title']}")
                print(f"     {item['url']}")
                print(f"     {item['description'][:100]}...")
                print()
        else:
            print(f"❌ Error: {data.get('error')}")
        
        # Show stats
        client = await get_client()
        stats = client.get_stats()
        print(f"\n📊 Stats:")
        print(f"  Daily requests: {stats['daily_requests']}/{stats['daily_limit']}")
        print(f"  Cache hit rate: {stats['cache']['hit_rate']:.1%}")
        print(f"  Healthy instances: {stats['pool']['healthy']}/{stats['pool']['total']}")
        
        await close_client()
    
    asyncio.run(test())
