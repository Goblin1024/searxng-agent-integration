"""Anti-detection utilities for web scraping."""

import random
from typing import Dict, List, Optional


class AntiDetect:
    """Provides anti-detection capabilities for HTTP requests."""
    
    # Real browser User-Agent strings
    USER_AGENTS = [
        # Chrome on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        # Chrome on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        # Firefox on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0",
        # Firefox on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0",
        # Safari on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        # Edge on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        # Chrome on Linux
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        # Firefox on Linux
        "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/121.0",
    ]
    
    # Accept headers
    ACCEPT_HEADERS = [
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    ]
    
    # Accept-Language headers
    ACCEPT_LANGUAGES = [
        "en-US,en;q=0.9",
        "en-GB,en;q=0.8",
        "en-US,en;q=0.5",
        "en;q=0.9",
        "zh-CN,zh;q=0.9,en;q=0.8",
        "ja-JP,ja;q=0.9,en;q=0.8",
    ]
    
    # Accept-Encoding headers
    ACCEPT_ENCODINGS = [
        "gzip, deflate, br",
        "gzip, deflate",
    ]
    
    def __init__(self, enabled: bool = True):
        """Initialize anti-detection.
        
        Args:
            enabled: Whether anti-detection is enabled
        """
        self.enabled = enabled
        self._ua_index = random.randint(0, len(self.USER_AGENTS) - 1)
    
    def get_headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Generate realistic browser headers.
        
        Args:
            extra: Additional headers to include
            
        Returns:
            Dictionary of HTTP headers
        """
        if not self.enabled:
            return extra or {}
        
        # Rotate User-Agent
        self._ua_index = (self._ua_index + random.randint(1, 3)) % len(self.USER_AGENTS)
        
        headers = {
            "User-Agent": self.USER_AGENTS[self._ua_index],
            "Accept": random.choice(self.ACCEPT_HEADERS),
            "Accept-Language": random.choice(self.ACCEPT_LANGUAGES),
            "Accept-Encoding": random.choice(self.ACCEPT_ENCODINGS),
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }
        
        if extra:
            headers.update(extra)
        
        return headers
    
    def get_random_ua(self) -> str:
        """Get a random User-Agent string."""
        return random.choice(self.USER_AGENTS)
    
    def add_referer(self, headers: Dict[str, str], referer: str) -> Dict[str, str]:
        """Add referer header to existing headers."""
        headers["Referer"] = referer
        return headers
