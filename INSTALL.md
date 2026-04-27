# Hermes Agent SearXNG 集成安装指南

## 🎯 目标

当 Hermes Agent 的付费搜索 API（Firecrawl、Parallel、Exa、Tavily）用完额度或不可用时，自动回退到免费的 SearXNG 公共实例继续搜索。

## ✨ 特性

- **零配置回退**: 付费 API 不可用时自动切换到 SearXNG
- **无缝体验**: 用户无需更改使用方式，`web_search` 始终可用
- **反爬保护**: 多实例轮换、请求头伪装、速率限制
- **无需 API Key**: SearXNG 使用公共实例，完全免费

## 📦 安装步骤

### 1. 确保 Hermes Agent 已安装

```bash
# 检查 hermes 命令是否可用
hermes --version
```

### 2. 复制集成文件

```bash
# 进入 Hermes Agent tools 目录
cd ~/.hermes/tools  # 或你的 Hermes 安装路径/tools

# 复制 SearXNG 集成文件
cp /path/to/searxng_integration.py .

# 或者从 GitHub 下载
curl -L https://raw.githubusercontent.com/Goblin1024/searxng-agent-integration/main/searxng_integration.py -o searxng_integration.py
```

### 3. 修改 web_tools.py（关键步骤）

编辑 `hermes-agent/tools/web_tools.py`：

#### 3.1 修改 Firecrawl 导入（约第 50 行）

将：
```python
from firecrawl import Firecrawl
```

改为：
```python
try:
    from firecrawl import Firecrawl
except ImportError:
    Firecrawl = None
```

#### 3.2 修改 check_firecrawl_api_key 函数（约第 1962 行）

在函数开头添加：
```python
def check_firecrawl_api_key() -> bool:
    # Firecrawl package not installed
    if Firecrawl is None:
        return False
    # ... rest of function
```

#### 3.3 修改 _get_firecrawl_client 函数（约第 221 行）

在函数开头添加：
```python
def _get_firecrawl_client():
    # Check if Firecrawl is available
    if Firecrawl is None:
        raise ImportError("Firecrawl package not installed")
    # ... rest of function
```

#### 3.4 修改 check_web_api_key 函数（约第 1977 行）

将函数改为始终返回 True：
```python
def check_web_api_key() -> bool:
    """Check whether the configured web backend is available.
    
    Always returns True because SearXNG fallback is always available.
    """
    configured = _load_web_config().get("backend", "").lower().strip()
    if configured in ("exa", "parallel", "firecrawl", "tavily"):
        return _is_backend_available(configured)
    # Check if any paid backend is available
    paid_available = any(_is_backend_available(backend) for backend in ("exa", "parallel", "firecrawl", "tavily"))
    if paid_available:
        return True
    # SearXNG is always available as fallback
    return True
```

#### 3.5 修改 web_search_tool 函数的异常处理（约第 1154 行）

在 except 块中添加 SearXNG 回退：
```python
    except Exception as e:
        error_msg = f"Error searching web: {str(e)}"
        logger.warning("%s", error_msg)
        
        # ── SearXNG Fallback ──────────────────────────────────────────
        try:
            logger.info("Attempting SearXNG fallback search...")
            from tools.searxng_integration import SearXNGClient
            
            searxng_client = SearXNGClient()
            searxng_result = asyncio.run(searxng_client.search(query, limit))
            
            if searxng_result.get("success"):
                logger.info("SearXNG fallback successful")
                response_data = {
                    "success": True,
                    "data": {
                        "web": searxng_result["data"]["web"]
                    }
                }
                return json.dumps(response_data, indent=2, ensure_ascii=False)
        except Exception as fallback_error:
            logger.error("SearXNG fallback error: %s", fallback_error)
        
        return tool_error(error_msg)
```

### 4. 重启 Hermes Agent

```bash
# 完全退出 Hermes
# 然后重新启动
hermes
```

### 5. 验证安装

```bash
# 检查 web_search 工具是否可用
hermes tools

# 应该能看到 web_search 带有 🔍 图标

# 测试搜索（即使没有 API key）
> 搜索 Python 异步编程
```

## 🔧 工作原理

### 正常流程

```
用户搜索 → web_search → 检查付费 API → 使用付费 API → 返回结果
```

### 回退流程（付费 API 不可用）

```
用户搜索 → web_search → 检查付费 API → API 失败/无额度 
  → 捕获异常 → 调用 SearXNG → 返回免费结果
```

### 技术细节

1. **延迟导入**: Firecrawl 改为 try/except 导入，缺失时不影响其他功能
2. **check_fn 修改**: `check_web_api_key()` 始终返回 True，确保工具始终显示为可用
3. **异常回退**: `web_search_tool` 的 except 块自动调用 SearXNG
4. **透明体验**: 用户完全感知不到后端切换

## ⚙️ 可选配置

### 环境变量

```bash
# 调整 SearXNG 请求频率（默认 5 秒）
export SEARXNG_REQUEST_INTERVAL=3.0

# 调整每日上限（默认 500）
export SEARXNG_DAILY_LIMIT=1000

# 调整缓存时间（默认 600 秒）
export SEARXNG_CACHE_TTL=300
```

### Hermes 配置

编辑 `~/.hermes/config.yaml`：

```yaml
searxng:
  request_interval: 5.0
  daily_limit: 500
  cache_ttl: 600
```

## 🛡️ 反爬保护

SearXNG 集成包含多层保护：

1. **实例轮换**: 20+ 公共实例自动切换
2. **请求头伪装**: 7+ 真实浏览器 User-Agent
3. **会话模拟**: 先访问首页获取 cookies，再搜索
4. **速率限制**: Token bucket + 随机抖动
5. **指数退避**: 失败时渐进式延迟重试

## 📊 性能

| 场景 | 响应时间 | 说明 |
|------|----------|------|
| 付费 API 可用 | 1-3s | 正常使用付费 API |
| 付费 API 不可用 | 3-6s | 自动回退到 SearXNG |
| 缓存命中 | 0.1s | 重复查询直接返回 |

## 🐛 故障排除

### web_search 仍然显示不可用

```bash
# 检查 searxng_integration.py 是否在 tools 目录
ls ~/.hermes/tools/searxng_integration.py

# 检查 web_tools.py 是否已修改
grep "SearXNG Fallback" ~/.hermes/tools/web_tools.py
```

### SearXNG 返回空结果

- 等待 10-15 分钟后重试（实例可能被临时限制）
- 检查网络连接
- 尝试不同的搜索关键词

### 安装后 Hermes 无法启动

```bash
# 检查语法错误
python3 -m py_compile ~/.hermes/tools/web_tools.py

# 检查导入错误
python3 -c "import sys; sys.path.insert(0, '~/.hermes/tools'); import searxng_integration"
```

## 📝 更新日志

### v2.0 (当前版本)
- ✅ 深度集成到 web_search，自动回退
- ✅ 无需修改用户使用方式
- ✅ 支持 Firecrawl 缺失环境
- ✅ 改进的错误处理

### v1.0
- ✅ 基础 SearXNG 集成
- ✅ 独立工具 `searxng_search`
- ✅ 反爬保护
- ✅ 多实例管理

## 🤝 贡献

欢迎提交 Issue 和 PR！

## 📜 许可证

MIT License

## 🙏 致谢

- [SearXNG](https://github.com/searxng/searxng) - 免费元搜索引擎
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) - AI Agent 框架

---

**让搜索永远免费！** 🔎
