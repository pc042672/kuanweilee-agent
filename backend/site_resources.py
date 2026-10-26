"""
Per-site resource cache: query services, config managers, profilers.

Thread-safe cache with TTL. Each site gets its own isolated resources
built from its data_sources row (or GP_* env fallback) via dbtoolbox.
"""

import logging
import threading
import time
from dataclasses import dataclass, field

from config import ConfigManager
from dbtoolbox import QueryService, build_query_service
from tools.profiler import DatabaseProfiler

logger = logging.getLogger(__name__)


@dataclass
class SiteResources:
    """Cached resources for a single site."""
    query_service: QueryService
    profiler: DatabaseProfiler
    config_manager: ConfigManager
    created_at: float = field(default_factory=time.monotonic)


class SiteResourceManager:
    """Thread-safe cache of per-site resources with TTL eviction."""

    def __init__(self, ttl_seconds: int = 3600):
        self._cache: dict[int, SiteResources] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds

    def get(self, site_id: int) -> SiteResources:
        """Get or create cached resources for a site."""
        now = time.monotonic()

        # Fast path: check cache without lock
        cached = self._cache.get(site_id)
        if cached and (now - cached.created_at) < self._ttl:
            return cached

        # Slow path: create under lock (double-check)
        with self._lock:
            cached = self._cache.get(site_id)
            if cached and (now - cached.created_at) < self._ttl:
                return cached

            resources = self._create_resources(site_id)
            self._cache[site_id] = resources
            logger.info("Created resources for site_id=%d", site_id)
            return resources

    def _create_resources(self, site_id: int) -> SiteResources:
        """Build fresh resources for a site."""
        config_mgr = ConfigManager()
        query_service = build_query_service(site_id, config_mgr)
        return SiteResources(
            query_service=query_service,
            profiler=DatabaseProfiler(query_service),
            config_manager=config_mgr,
        )

    def evict(self, site_id: int) -> None:
        """Remove cached resources for a site (e.g. on config change)."""
        with self._lock:
            old = self._cache.pop(site_id, None)
            if old:
                old.query_service.source.dispose()
            logger.info("Evicted resources for site_id=%d", site_id)


_manager = SiteResourceManager()


def get_site_resources(site_id: int) -> SiteResources:
    """Get cached resources for a site. Convenience wrapper."""
    return _manager.get(site_id)


def evict_site_resources(site_id: int) -> None:
    """Evict cached resources for a site."""
    _manager.evict(site_id)
