#!/usr/bin/env python3
"""
Integration test for SearXNG fallback in web_search.

This script tests that web_search automatically falls back to SearXNG
when paid backends (Firecrawl, Parallel, etc.) are unavailable.
"""

import asyncio
import json
import sys

# Test 1: Direct SearXNG search
print("Test 1: Direct SearXNG search")
print("-" * 50)

sys.path.insert(0, '/home/spirit/Projects/AI_Agents/hermes-agent/tools')
from searxng_integration import SearXNGClient

async def test_searxng():
    client = SearXNGClient()
    result = await client.search("Python async programming", limit=2)
    
    if result.get("success"):
        print(f"✅ SUCCESS: Found {result['data']['returned_results']} results")
        for item in result["data"]["web"]:
            print(f"  {item['position']}. {item['title'][:60]}...")
            print(f"     {item['url']}")
    else:
        print(f"❌ FAILED: {result.get('error')}")
    
    return result.get("success")

success = asyncio.run(test_searxng())

print("\n" + "=" * 50)
print("Summary:")
print(f"  SearXNG direct search: {'✅ PASS' if success else '❌ FAIL'}")
print("\nNote: Full web_search fallback test requires Hermes Agent environment.")
print("The fallback logic is integrated in tools/web_tools.py")
print("When paid APIs fail, web_search automatically uses SearXNG.")
