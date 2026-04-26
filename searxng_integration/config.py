"""Configuration management for SearXNG integration."""

import os
from typing import Dict, List, Optional


class SearXNGConfig:
    """Configuration for SearXNG integration."""
    
    # Default public instances (updated periodically)
    DEFAULT_INSTANCES = [
        "https://search.sapti.me",
        "https://searx.be",
        "https://search.bus-hit.me",
        "https://search.projectsegfault.com",
        "https://search.inetol.net",
        "https://searxng.nicfab.eu",
        "https://searx.tiekoetter.com",
        "https://searx.work",
        "https://searx.prvcy.eu",
        "https://search.snopyta.org",
    ]
    
    # Rate limiting
    DEFAULT_REQUEST_INTERVAL = 3.0  # seconds between requests per instance
    DEFAULT_BURST = 3  # burst capacity
    DEFAULT_JITTER_MAX = 2.0  # max jitter in seconds
    
    # Timeouts
    DEFAULT_TIMEOUT = 30  # request timeout in seconds
    DEFAULT_CONNECT_TIMEOUT = 10
    
    # Retry settings
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 2.0  # base delay in seconds
    
    # Cache settings
    DEFAULT_CACHE_TTL = 300  # 5 minutes
    DEFAULT_CACHE_MAX_SIZE = 1000  # max cached items
    
    # Instance pool settings
    DEFAULT_HEALTH_CHECK_INTERVAL = 300  # 5 minutes
    DEFAULT_INSTANCE_TIMEOUT = 10  # instance health check timeout
    DEFAULT_MAX_FAILURES = 5  # max failures before marking unhealthy
    DEFAULT_COOLDOWN_DURATION = 300  # 5 minutes cooldown after rate limit
    
    # Daily limits for self-protection
    DEFAULT_DAILY_LIMIT = 500
    
    # Feature flags
    DEFAULT_AUTO_DISCOVER = True
    DEFAULT_USER_AGENT_ROTATION = True
    DEFAULT_CACHE_ENABLED = True
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        self.instances = self._get_instances()
        self.request_interval = float(os.getenv("SEARXNG_REQUEST_INTERVAL", self.DEFAULT_REQUEST_INTERVAL))
        self.burst = int(os.getenv("SEARXNG_BURST", self.DEFAULT_BURST))
        self.jitter_max = float(os.getenv("SEARXNG_JITTER_MAX", self.DEFAULT_JITTER_MAX))
        self.timeout = int(os.getenv("SEARXNG_TIMEOUT", self.DEFAULT_TIMEOUT))
        self.connect_timeout = int(os.getenv("SEARXNG_CONNECT_TIMEOUT", self.DEFAULT_CONNECT_TIMEOUT))
        self.max_retries = int(os.getenv("SEARXNG_MAX_RETRIES", self.DEFAULT_MAX_RETRIES))
        self.retry_delay = float(os.getenv("SEARXNG_RETRY_DELAY", self.DEFAULT_RETRY_DELAY))
        self.cache_ttl = int(os.getenv("SEARXNG_CACHE_TTL", self.DEFAULT_CACHE_TTL))
        self.cache_max_size = int(os.getenv("SEARXNG_CACHE_MAX_SIZE", self.DEFAULT_CACHE_MAX_SIZE))
        self.health_check_interval = int(os.getenv("SEARXNG_HEALTH_CHECK_INTERVAL", self.DEFAULT_HEALTH_CHECK_INTERVAL))
        self.instance_timeout = int(os.getenv("SEARXNG_INSTANCE_TIMEOUT", self.DEFAULT_INSTANCE_TIMEOUT))
        self.max_failures = int(os.getenv("SEARXNG_MAX_FAILURES", self.DEFAULT_MAX_FAILURES))
        self.cooldown_duration = int(os.getenv("SEARXNG_COOLDOWN_DURATION", self.DEFAULT_COOLDOWN_DURATION))
        self.daily_limit = int(os.getenv("SEARXNG_DAILY_LIMIT", self.DEFAULT_DAILY_LIMIT))
        self.auto_discover = os.getenv("SEARXNG_AUTO_DISCOVER", "true").lower() == "true"
        self.user_agent_rotation = os.getenv("SEARXNG_USER_AGENT_ROTATION", "true").lower() == "true"
        self.cache_enabled = os.getenv("SEARXNG_CACHE_ENABLED", "true").lower() == "true"
    
    def _get_instances(self) -> List[str]:
        """Get SearXNG instances from environment or use defaults."""
        env_instances = os.getenv("SEARXNG_INSTANCES", "").strip()
        if env_instances:
            return [url.strip() for url in env_instances.split(",") if url.strip()]
        return self.DEFAULT_INSTANCES.copy()
    
    @classmethod
    def from_dict(cls, config: Dict) -> "SearXNGConfig":
        """Create config from dictionary (for integration with hermes config)."""
        instance = cls()
        instance.instances = config.get("instances", instance.instances)
        instance.request_interval = config.get("request_interval", instance.request_interval)
        instance.burst = config.get("burst", instance.burst)
        instance.jitter_max = config.get("jitter_max", instance.jitter_max)
        instance.timeout = config.get("timeout", instance.timeout)
        instance.max_retries = config.get("max_retries", instance.max_retries)
        instance.cache_ttl = config.get("cache_ttl", instance.cache_ttl)
        instance.daily_limit = config.get("daily_limit", instance.daily_limit)
        instance.auto_discover = config.get("auto_discover", instance.auto_discover)
        instance.user_agent_rotation = config.get("user_agent_rotation", instance.user_agent_rotation)
        instance.cache_enabled = config.get("cache_enabled", instance.cache_enabled)
        return instance


# Global config instance
_config = None


def get_config() -> SearXNGConfig:
    """Get or create global config instance."""
    global _config
    if _config is None:
        _config = SearXNGConfig()
    return _config


def set_config(config: SearXNGConfig) -> None:
    """Set global config instance."""
    global _config
    _config = config
