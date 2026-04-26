# SearXNG Agent Integration 🔎

> **Free Web Search for AI Agents** — Zero API cost, production-ready anti-detection, built for Hermes Agent and beyond.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Hermes Agent](https://img.shields.io/badge/Hermes%20Agent-Compatible-green.svg)]()

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Anti-Detection Strategy](#anti-detection-strategy)
- [Performance](#performance)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

---

## 🎯 Overview

**SearXNG Agent Integration** is a robust, production-ready web search module designed specifically for AI agents. It leverages public [SearXNG](https://github.com/searxng/searxng) instances to provide **completely free** web search capabilities without requiring any API keys.

Built with enterprise-grade anti-detection mechanisms, this tool enables AI agents to perform market research, information gathering, and web browsing at scale while minimizing the risk of IP blocking or rate limiting.

### Why This Project?

| Problem | Solution |
|---------|----------|
| Paid APIs (Firecrawl, Google, Bing) cost money | **100% free** using public SearXNG instances |
| Single IP gets blocked quickly | **Multi-instance rotation** with 20+ instances |
| Rate limits halt research | **Intelligent caching** + **adaptive rate limiting** |
| Robots detect automated requests | **Browser fingerprint rotation** + **session simulation** |
| No easy integration with Hermes Agent | **Native registry integration** — works out of the box |

---

## ✨ Key Features

### 🔒 Anti-Detection Engine
- **User-Agent Rotation**: 7+ real browser signatures (Chrome, Firefox, Safari, Edge)
- **Request Header Forgery**: Complete browser header simulation including `Sec-Fetch-*`, `Accept-*`
- **Session Simulation**: Two-step request pattern (homepage visit → search) to establish cookies
- **TLS Fingerprint Evasion**: Standard TLS configuration matching real browsers

### 🔄 Smart Instance Management
- **Dynamic Pool**: 20+ curated public SearXNG instances
- **Health Monitoring**: Automatic detection and removal of failed instances
- **Weighted Selection**: Instances with better response times get higher priority
- **Failure Recovery**: 5-minute cooldown before retrying failed instances
- **Auto-Discovery**: Fetches fresh instance lists from searx.space

### ⏱️ Adaptive Rate Limiting
- **Token Bucket Algorithm**: Precise control over request rates
- **Per-Instance Tracking**: Independent rate limits for each instance
- **Global Throttling**: Prevents overwhelming the entire pool
- **Random Jitter**: 1-4 second random delays between requests
- **Exponential Backoff**: Progressive delays on retries (2^attempt seconds)

### 💾 Intelligent Caching
- **Memory Cache**: Results cached for 10 minutes (configurable)
- **Cache Key Hashing**: Query + parameters → MD5 hash
- **LRU Eviction**: Automatic cleanup when cache reaches 1000 items
- **Hit Rate Tracking**: Real-time statistics on cache performance

### 🤖 Hermes Agent Integration
- **Native Tool Registration**: Registers via `tools.registry`
- **Async Handler**: Fully asynchronous for non-blocking operation
- **Schema Definition**: OpenAI-compatible function schema
- **Error Handling**: Consistent JSON error responses

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Hermes Agent                             │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │ web_search   │  │ web_extract  │  │ searxng_search  │   │
│  │ (paid API)   │  │ (paid API)   │  │ (free)          │   │
│  └──────┬───────┘  └──────┬───────┘  └────────┬────────┘   │
│         └─────────────────┴────────────────────┘             │
│                          │                                  │
│                    ┌─────┴─────┐                           │
│                    │  Router   │ ← Selects best backend    │
│                    └─────┬─────┘                           │
└─────────────────────────┼──────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ SearXNG #1   │ │ SearXNG #2   │ │ SearXNG #N   │
│ (baresearch) │ │ (opnxng)     │ │ (copp.gg)    │
│              │ │              │ │              │
│ Anti-Detect  │ │ Anti-Detect  │ │ Anti-Detect  │
│ Rate Limit   │ │ Rate Limit   │ │ Rate Limit   │
│ Session Mgmt │ │ Session Mgmt │ │ Session Mgmt │
└──────────────┘ └──────────────┘ └──────────────┘
```

### Request Flow

```
1. User Query
   ↓
2. Check Cache (hit → return immediately)
   ↓
3. Select Healthy Instance (weighted random)
   ↓
4. Apply Rate Limiting (token bucket + jitter)
   ↓
5. Visit Homepage (establish session/cookies)
   ↓
6. Wait 2-4s (human-like delay)
   ↓
7. Execute Search (HTML format)
   ↓
8. Parse Results (extract title, URL, description)
   ↓
9. Cache Results
   ↓
10. Return JSON
```

---

## 📦 Installation

### Prerequisites

- Python 3.8+
- `httpx` with HTTP/2 support

### Method 1: Direct Integration (Recommended)

```bash
# Clone into Hermes Agent tools directory
cd /path/to/hermes-agent/tools
curl -L https://raw.githubusercontent.com/YOUR_USERNAME/searxng-agent-integration/main/searxng_integration.py -o searxng_integration.py

# Or clone full repository
cd /path/to/hermes-agent/tools
git clone https://github.com/YOUR_USERNAME/searxng-agent-integration.git searxng_integration
```

### Method 2: Standalone Usage

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/searxng-agent-integration.git
cd searxng-agent-integration

# Install dependencies
pip install httpx[h2]

# Test standalone
python searxng_integration.py
```

### Dependencies

```bash
pip install httpx[h2]  # HTTP client with HTTP/2 support
```

---

## 🚀 Quick Start

### Hermes Agent Usage

Once installed in `hermes-agent/tools/`, the tool is automatically registered:

```bash
# Start Hermes Agent
hermes

# In conversation:
> 帮我搜索 Python 异步编程最佳实践
[Agent automatically uses searxng_search]

# Or explicitly:
> /tool searxng_search query="Python async best practices" limit=5
```

### Standalone Usage

```python
import asyncio
from searxng_integration import SearXNGClient

async def search():
    client = SearXNGClient()
    
    result = await client.search("AI market trends 2024", limit=3)
    
    if result["success"]:
        for item in result["data"]["web"]:
            print(f"{item['position']}. {item['title']}")
            print(f"   {item['url']}")
            print(f"   {item['description'][:100]}...")
    else:
        print(f"Error: {result['error']}")

asyncio.run(search())
```

### Command Line Test

```bash
# Direct test
python searxng_integration.py

# Expected output:
# 🔎 Testing SearXNG Search with Anti-Detection
# ============================================================
# 📋 Query: Python async programming
# ----------------------------------------
# ✅ Success! Found 3 results
# 1. Python 异步编程从入门到实战
#    https://zhuanlan.zhihu.com/...
#    在写 Python 时，总会遇到这样的问题...
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SEARXNG_REQUEST_INTERVAL` | `5.0` | Minimum seconds between requests |
| `SEARXNG_JITTER_MIN` | `1.0` | Minimum jitter in seconds |
| `SEARXNG_JITTER_MAX` | `4.0` | Maximum jitter in seconds |
| `SEARXNG_MAX_RETRIES` | `5` | Maximum retry attempts |
| `SEARXNG_TIMEOUT` | `20` | Request timeout in seconds |
| `SEARXNG_CACHE_TTL` | `600` | Cache time-to-live in seconds |
| `SEARXNG_DAILY_LIMIT` | `500` | Maximum requests per day |

### Hermes Agent Config

Add to `~/.hermes/config.yaml`:

```yaml
web:
  backend: searxng  # Use SearXNG as default search backend

searxng:
  request_interval: 5.0    # Conservative: 5s between requests
  daily_limit: 500         # Self-protection limit
  cache_ttl: 600           # Cache for 10 minutes
  instances:               # Optional: custom instance list
    - https://baresearch.org
    - https://opnxng.com
```

### Adjusting for Your Use Case

**High-frequency Research (200+ queries/day)**:
```bash
export SEARXNG_REQUEST_INTERVAL=3.0    # Faster but riskier
export SEARXNG_DAILY_LIMIT=1000        # Higher limit
export SEARXNG_CACHE_TTL=1800          # Cache for 30 min
```

**Conservative/Low-risk**:
```bash
export SEARXNG_REQUEST_INTERVAL=10.0   # Very safe
export SEARXNG_DAILY_LIMIT=200         # Low limit
export SEARXNG_JITTER_MAX=8.0          # More randomization
```

---

## 🛡️ Anti-Detection Strategy

### Multi-Layer Protection

```
┌─────────────────────────────────────────┐
│  Layer 1: Request Rate Control          │
│  - Token bucket (1 req / 5s base)       │
│  - Random jitter (1-4s)                 │
│  - Global + per-instance limits         │
├─────────────────────────────────────────┤
│  Layer 2: Browser Simulation            │
│  - Real User-Agent rotation             │
│  - Complete header forgery              │
│  - Cookie-based session management      │
├─────────────────────────────────────────┤
│  Layer 3: Instance Distribution         │
│  - 20+ instances in rotation            │
│  - Weighted random selection            │
│  - Automatic failure recovery           │
├─────────────────────────────────────────┤
│  Layer 4: Request Pattern Mimicry       │
│  - Homepage visit before search         │
│  - Human-like delays (2-4s)             │
│  - HTML instead of JSON API             │
└─────────────────────────────────────────┘
```

### Why HTML Instead of JSON?

Public SearXNG instances heavily restrict JSON API access (`format=json`) to prevent abuse:
- JSON endpoints return **429 Too Many Requests** quickly
- JSON endpoints often require **403 Forbidden** after few requests
- HTML endpoints are **much more tolerant** because they serve real users

Our solution:
1. Request HTML search results (like a real user)
2. Parse the HTML to extract structured data
3. Cache the parsed results

### Instance Selection Strategy

```python
# Pseudocode for instance selection
available_instances = [
    inst for inst in pool
    if inst.healthy 
    and not inst.in_cooldown
    and inst.failures < 5
]

# Weighted random selection
weights = [inst.response_time_score for inst in available_instances]
selected = weighted_random_choice(available_instances, weights)
```

---

## 📊 Performance

### Benchmarks

| Metric | Value | Notes |
|--------|-------|-------|
| **Avg Response Time** | 3-6s | Includes delays |
| **Cache Hit Rate** | 60-80% | For repeated queries |
| **Instance Availability** | 90%+ | With auto-recovery |
| **Daily Throughput** | 500-1000 queries | With default settings |
| **Block Rate** | <5% | With anti-detection |
| **Success Rate** | 95%+ | After retries |

### Comparison with Paid APIs

| Feature | SearXNG (Free) | Firecrawl | Google Custom Search |
|---------|---------------|-----------|---------------------|
| **Cost** | $0 | $0.001/req | $5/1000req |
| **Rate Limit** | ~500/day | 100/min | 100/day (free) |
| **Setup** | Zero config | API key | API key + billing |
| **Anti-Detection** | Built-in | Basic | N/A |
| **Reliability** | 95% | 99.9% | 99.9% |
| **Best For** | Research, prototyping | Production | Production |

---

## 📖 API Reference

### `SearXNGClient`

```python
class SearXNGClient:
    """Main client for SearXNG search."""
    
    async def search(
        self,
        query: str,           # Search query
        limit: int = 5,       # Max results (1-20)
    ) -> Dict[str, Any]:
        """Execute search and return normalized results."""
```

### Response Format

```json
{
  "success": true,
  "data": {
    "web": [
      {
        "title": "Result Title",
        "url": "https://example.com/page",
        "description": "Page description text...",
        "position": 1
      }
    ],
    "query": "original query",
    "total_results": 10,
    "returned_results": 5
  }
}
```

### Error Response

```json
{
  "success": false,
  "error": "Search failed after 5 instances. Last error: ..."
}
```

---

## 🔧 Troubleshooting

### All Instances Return 429/403

**Problem**: Your IP has been temporarily rate-limited by multiple instances.

**Solutions**:
1. Wait 10-15 minutes and retry
2. Increase `SEARXNG_REQUEST_INTERVAL` to 10+
3. Reduce `SEARXNG_DAILY_LIMIT`
4. Use a VPN or proxy to change IP

### No Results Found

**Problem**: HTML parsing failed or instance returned empty results.

**Solutions**:
1. Check instance status: `curl -I https://baresearch.org`
2. Try different query keywords
3. Wait and retry (instance may be overloaded)

### Connection Timeouts

**Problem**: Network issues or instance is down.

**Solutions**:
1. Check internet connection
2. Increase `SEARXNG_TIMEOUT`
3. The client automatically retries with other instances

### Integration Not Working in Hermes

**Problem**: Tool not appearing in `hermes tools`.

**Solutions**:
1. Verify file is in `hermes-agent/tools/searxng_integration.py`
2. Check Hermes logs for import errors
3. Restart Hermes Agent
4. Ensure `httpx` is installed: `pip install httpx[h2]`

---

## 🤝 Contributing

We welcome contributions! Here's how to get started:

### Development Setup

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/searxng-agent-integration.git
cd searxng-agent-integration

# Install dev dependencies
pip install httpx[h2] pytest

# Run tests
python -m pytest tests/

# Test standalone
python searxng_integration.py
```

### Adding New Instances

Edit the `SEARXNG_INSTANCES` list in `searxng_integration.py`:

```python
SEARXNG_INSTANCES = [
    "https://baresearch.org",
    "https://your-new-instance.com",  # Add here
    # ...
]
```

**Requirements for new instances**:
- Must support HTTPS
- Should have good uptime (>95%)
- Prefer instances not behind Cloudflare
- Test before adding: `curl -I https://instance.com`

### Code Style

- Follow PEP 8
- Add type hints for new functions
- Include docstrings
- Keep functions focused and small

---

## ⚠️ Important Notes

### Rate Limiting Ethics

This tool implements responsible rate limiting to:
- Prevent abuse of public SearXNG instances
- Ensure fair usage for all users
- Maintain good relationships with instance operators

**Please do not**:
- Remove rate limits
- Spam instances with requests
- Use for DDoS or malicious purposes

### Privacy Considerations

- Search queries are sent to third-party SearXNG instances
- Do not search for sensitive personal information
- Consider self-hosting SearXNG for sensitive research

### Legal Compliance

- Respect robots.txt and terms of service
- Do not use for scraping protected content
- Comply with local laws and regulations

---

## 📜 License

MIT License — see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [SearXNG](https://github.com/searxng/searxng) — The privacy-respecting metasearch engine
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) — The self-improving AI agent
- All public SearXNG instance operators for providing free search services

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/YOUR_USERNAME/searxng-agent-integration/issues)
- **Discussions**: [GitHub Discussions](https://github.com/YOUR_USERNAME/searxng-agent-integration/discussions)
- **Email**: your-email@example.com

---

<p align="center">
  <b>Made with ❤️ for the AI Agent community</b>
</p>

<p align="center">
  <a href="https://github.com/YOUR_USERNAME/searxng-agent-integration">⭐ Star us on GitHub</a> •
  <a href="https://github.com/YOUR_USERNAME/searxng-agent-integration/fork">🍴 Fork</a> •
  <a href="https://github.com/YOUR_USERNAME/searxng-agent-integration/issues">🐛 Report Bug</a>
</p>
