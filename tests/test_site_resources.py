"""Tests for backend/site_resources.py — SiteResourceManager cache."""

import time

from site_resources import SiteResourceManager, SiteResources


class TestSiteResourceManager:
    def test_creates_resources_on_first_call(self):
        mgr = SiteResourceManager()
        res = mgr.get(site_id=1)
        assert isinstance(res, SiteResources)
        assert res.query_service is not None
        assert res.profiler is not None
        assert res.config_manager is not None

    def test_returns_cached_on_second_call(self):
        mgr = SiteResourceManager()
        res1 = mgr.get(site_id=1)
        res2 = mgr.get(site_id=1)
        assert res1 is res2

    def test_different_sites_get_different_resources(self):
        mgr = SiteResourceManager()
        res1 = mgr.get(site_id=1)
        res2 = mgr.get(site_id=2)
        assert res1 is not res2

    def test_evict_removes_cache(self):
        mgr = SiteResourceManager()
        res1 = mgr.get(site_id=1)
        mgr.evict(site_id=1)
        res2 = mgr.get(site_id=1)
        assert res1 is not res2

    def test_evict_disposes_source(self):
        mgr = SiteResourceManager()
        res = mgr.get(site_id=1)
        disposed = []
        res.query_service.source.dispose = lambda: disposed.append(True)
        mgr.evict(site_id=1)
        assert disposed == [True]

    def test_ttl_evicts_expired(self):
        mgr = SiteResourceManager(ttl_seconds=0)
        res1 = mgr.get(site_id=1)
        time.sleep(0.01)
        res2 = mgr.get(site_id=1)
        assert res1 is not res2

    def test_env_var_fallback_creates_query_service(self):
        """No app DB / no data_sources row → env-var Greenplum source."""
        mgr = SiteResourceManager()
        res = mgr.get(site_id=99)
        assert res.query_service.source.config.db_type == "greenplum"
        assert res.profiler.service is res.query_service
