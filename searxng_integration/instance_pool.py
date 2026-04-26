"""Instance pool management for SearXNG public instances."""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import httpx

from config import get_config

logger = logging.getLogger(__name__)


@dataclass
class InstanceStatus:
    """Status of a SearXNG instance."""
    url: str
    is_healthy: bool = True
    weight: float = 1.0
    failure_count: int = 0
    last_check: float = field(default_factory=time.time)
    last_failure: Optional[float] = None
    cooldown_until: Optional[float] = None
    response_time_ms: float = 0.0
    success_count: int = 0
    
    def is_in_cooldown(self) -> bool:
        """Check if instance is in cooldown period."""
        if self.cooldown_until is None:
            return False
        return time.time() < self.cooldown_until
    
    def can_use(self) -> bool:
        """Check if instance can be used."""
        return self.is_healthy and not self.is_in_cooldown()


class InstancePool:
    """Manages a pool of SearXNG public instances."""
    
    def __init__(self, instances: Optional[List[str]] = None):
        """Initialize instance pool.
        
        Args:
            instances: List of instance URLs (uses config defaults if None)
        """
        self.config = get_config()
        self.instances: Dict[str, InstanceStatus] = {}
        
        # Initialize with provided or default instances
        urls = instances or self.config.instances
        for url in urls:
            self.instances[url] = InstanceStatus(url=url)
        
        self._health_check_task: Optional[asyncio.Task] = None
        self._discovery_task: Optional[asyncio.Task] = None
        self._started = False
    
    async def start(self) -> None:
        """Start background tasks."""
        if self._started:
            return
        
        self._started = True
        
        # Start health check loop
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        
        # Start instance discovery if enabled
        if self.config.auto_discover:
            self._discovery_task = asyncio.create_task(self._discovery_loop())
        
        logger.info(f"Instance pool started with {len(self.instances)} instances")
    
    async def stop(self) -> None:
        """Stop background tasks."""
        self._started = False
        
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        if self._discovery_task:
            self._discovery_task.cancel()
            try:
                await self._discovery_task
            except asyncio.CancelledError:
                pass
    
    def get_healthy_instance(self) -> str:
        """Get a healthy instance using weighted random selection.
        
        Returns:
            URL of a healthy instance
            
        Raises:
            NoHealthyInstance: If no healthy instances available
        """
        healthy = [
            inst for inst in self.instances.values()
            if inst.can_use()
        ]
        
        if not healthy:
            # Try to find any instance that's not permanently failed
            fallback = [
                inst for inst in self.instances.values()
                if not inst.is_in_cooldown()
            ]
            if fallback:
                healthy = fallback
            else:
                raise NoHealthyInstance("No healthy instances available")
        
        # Weighted random selection
        weights = [inst.weight for inst in healthy]
        total_weight = sum(weights)
        
        if total_weight == 0:
            return random.choice(healthy).url
        
        r = random.uniform(0, total_weight)
        cumulative = 0
        for inst in healthy:
            cumulative += inst.weight
            if r <= cumulative:
                return inst.url
        
        return healthy[-1].url
    
    def get_all_instances(self) -> List[str]:
        """Get all instance URLs."""
        return list(self.instances.keys())
    
    def get_healthy_count(self) -> int:
        """Get number of healthy instances."""
        return sum(1 for inst in self.instances.values() if inst.can_use())
    
    def mark_unhealthy(self, url: str) -> None:
        """Mark an instance as unhealthy."""
        if url in self.instances:
            inst = self.instances[url]
            inst.is_healthy = False
            inst.failure_count += 1
            inst.last_failure = time.time()
            inst.weight = max(0.1, inst.weight * 0.5)  # Reduce weight
            
            logger.warning(f"Instance marked unhealthy: {url} (failures: {inst.failure_count})")
            
            # If too many failures, remove instance
            if inst.failure_count >= self.config.max_failures:
                logger.error(f"Removing instance due to too many failures: {url}")
                del self.instances[url]
    
    def mark_healthy(self, url: str, response_time_ms: float = 0) -> None:
        """Mark an instance as healthy."""
        if url in self.instances:
            inst = self.instances[url]
            inst.is_healthy = True
            inst.failure_count = 0
            inst.last_failure = None
            inst.success_count += 1
            inst.response_time_ms = response_time_ms
            # Gradually restore weight
            inst.weight = min(1.0, inst.weight * 1.2)
            inst.last_check = time.time()
    
    def cooldown(self, url: str, duration: Optional[int] = None) -> None:
        """Put an instance in cooldown."""
        if url in self.instances:
            duration = duration or self.config.cooldown_duration
            self.instances[url].cooldown_until = time.time() + duration
            logger.info(f"Instance in cooldown: {url} for {duration}s")
    
    def add_instance(self, url: str) -> None:
        """Add a new instance to the pool."""
        if url not in self.instances:
            self.instances[url] = InstanceStatus(url=url)
            logger.info(f"Added instance: {url}")
    
    def remove_instance(self, url: str) -> bool:
        """Remove an instance from the pool.
        
        Returns:
            True if instance was removed
        """
        if url in self.instances:
            del self.instances[url]
            logger.info(f"Removed instance: {url}")
            return True
        return False
    
    async def _health_check_loop(self) -> None:
        """Background task to check instance health."""
        while self._started:
            try:
                await self._check_all_instances()
                await asyncio.sleep(self.config.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(60)
    
    async def _check_all_instances(self) -> None:
        """Check health of all instances."""
        tasks = []
        for url in list(self.instances.keys()):
            tasks.append(self._check_instance(url))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _check_instance(self, url: str) -> None:
        """Check health of a single instance."""
        try:
            start = time.time()
            async with httpx.AsyncClient(timeout=self.config.instance_timeout) as client:
                response = await client.head(f"{url}/healthz", follow_redirects=True)
                elapsed = (time.time() - start) * 1000
                
                if response.status_code < 400:
                    self.mark_healthy(url, elapsed)
                else:
                    self.mark_unhealthy(url)
        except Exception as e:
            logger.debug(f"Health check failed for {url}: {e}")
            self.mark_unhealthy(url)
    
    async def _discovery_loop(self) -> None:
        """Background task to discover new public instances."""
        while self._started:
            try:
                await self._discover_instances()
                # Run discovery every 30 minutes
                await asyncio.sleep(1800)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Discovery error: {e}")
                await asyncio.sleep(600)
    
    async def _discover_instances(self) -> None:
        """Discover new SearXNG instances from public lists."""
        # List of sources for SearXNG instances
        sources = [
            "https://searx.space/data/instances.json",
        ]
        
        discovered: Set[str] = set()
        
        for source in sources:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.get(source)
                    if response.status_code == 200:
                        data = response.json()
                        # Parse instance list
                        if isinstance(data, dict):
                            for url, info in data.get("instances", {}).items():
                                if isinstance(info, dict) and info.get("version"):
                                    discovered.add(url.rstrip("/"))
            except Exception as e:
                logger.debug(f"Failed to discover from {source}: {e}")
        
        # Add new instances
        added = 0
        for url in discovered:
            if url not in self.instances and len(self.instances) < 50:
                self.add_instance(url)
                added += 1
        
        if added > 0:
            logger.info(f"Discovered {added} new instances")
    
    def get_status(self) -> Dict[str, Any]:
        """Get pool status."""
        return {
            "total": len(self.instances),
            "healthy": self.get_healthy_count(),
            "instances": {
                url: {
                    "healthy": inst.is_healthy,
                    "weight": inst.weight,
                    "failures": inst.failure_count,
                    "response_time_ms": inst.response_time_ms,
                    "in_cooldown": inst.is_in_cooldown(),
                }
                for url, inst in self.instances.items()
            }
        }


class NoHealthyInstance(Exception):
    """Raised when no healthy instances are available."""
    pass
