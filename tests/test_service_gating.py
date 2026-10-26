"""Phase C: per-site service gating at the tool boundary.

Covers ServiceGatingPlugin (ADK tool path), fail-closed checks inside the
brand/persona tools, the 409 guards on the HTTP routers, and the gated_tools
map exposed by the integrations status API.

Import-path note: agent-path modules (plugins, brand_tools) resolve their
dependencies via bare imports at call time, so patches target the bare
module instances (services.credentials, persona.search). Routers use
backend.* imports, so their patches target backend.services.credentials.
"""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import services.credentials as bare_credentials
from revive_agent.plugins import ServiceGatingPlugin
from services.credentials import service_not_configured_result

from backend.auth import UserContext, get_current_user

SITE_ID = 5

_USER = UserContext(user_id=42, email="alice@example.com", name="Alice",
                    site_id=SITE_ID, role="admin")


def _run_plugin(tool_name: str):
    return asyncio.run(ServiceGatingPlugin().before_tool_callback(
        tool=SimpleNamespace(name=tool_name), tool_args={}, tool_context=None,
    ))


def _assert_refusal_shape(result: dict, service: str):
    assert result["success"] is False
    assert result["error_type"] == "service_not_configured"
    assert f"'{service}'" in result["error"]
    assert "Settings → Integrations" in result["suggestion"]


# ==================== ServiceGatingPlugin ====================

class TestServiceGatingPlugin:
    def test_non_gated_tool_passes(self, monkeypatch):
        monkeypatch.setattr(bare_credentials, "is_configured", lambda *a: False)
        assert _run_plugin("dry_run_sql_tool") is None

    def test_blocks_unconfigured_service(self, monkeypatch):
        monkeypatch.setattr(bare_credentials, "is_configured", lambda *a: False)
        result = _run_plugin("analyze_brand_tool")
        _assert_refusal_shape(result, "gemini")

    def test_allows_configured_service(self, monkeypatch):
        monkeypatch.setattr(bare_credentials, "is_configured", lambda *a: True)
        assert _run_plugin("analyze_brand_tool") is None
        assert _run_plugin("classify_persona_tool") is None

    def test_uses_site_id_from_context(self, monkeypatch):
        import revive_agent.tools._infra as infra

        seen = {}

        def fake_is_configured(site_id, service):
            seen["args"] = (site_id, service)
            return True

        monkeypatch.setattr(infra, "get_site_id", lambda: 7)
        monkeypatch.setattr(bare_credentials, "is_configured", fake_is_configured)
        _run_plugin("classify_persona_tool")
        assert seen["args"] == (7, "vertex_ai")

    def test_refusal_label_fallback_for_unknown_service(self):
        result = service_not_configured_result("some_tool", "no_such_service")
        assert "'no_such_service'" in result["error"]
        _assert_refusal_shape(result, "no_such_service")


# ==================== Fail-closed inside the tools ====================

class TestToolFailClosed:
    def test_analyze_brand_tool_refuses_without_gemini(self, monkeypatch):
        from revive_agent.tools.brand_tools import analyze_brand_tool

        monkeypatch.setattr(bare_credentials, "resolve_credentials", lambda *a: None)
        result = analyze_brand_tool("https://example.com")
        _assert_refusal_shape(result, "gemini")

    def test_analyze_brand_tool_passes_site_api_key(self, monkeypatch):
        import tools.brand_analyzer as analyzer
        from revive_agent.tools.brand_tools import analyze_brand_tool

        monkeypatch.setattr(
            bare_credentials, "resolve_credentials", lambda *a: {"api_key": "site-key-123"}
        )
        seen = {}

        def fake_sync(url, api_key=None):
            seen["api_key"] = api_key
            return {"success": False, "error": "stub"}

        monkeypatch.setattr(analyzer, "analyze_brand_sync", fake_sync)
        analyze_brand_tool("https://example.com")
        assert seen["api_key"] == "site-key-123"

    def test_classify_persona_tool_refuses_without_vertex(self, monkeypatch):
        from revive_agent.tools.persona_tools import classify_persona_tool

        monkeypatch.setattr(bare_credentials, "resolve_credentials", lambda *a: None)
        result = classify_persona_tool("premium electronics buyers")
        _assert_refusal_shape(result, "vertex_ai")

    def test_classify_persona_tool_passes_site_project(self, monkeypatch):
        import persona.search as search
        from revive_agent.tools.persona_tools import classify_persona_tool

        monkeypatch.setattr(
            bare_credentials, "resolve_credentials",
            lambda *a: {"project_id": "proj-x", "location": "asia-east1"},
        )
        seen = {}

        def fake_classify(content, top_k, category_filter=None, project_id=None, location=None):
            seen["project"] = (project_id, location)
            return SimpleNamespace(model_dump=lambda: {"archetypes": [], "top_matches": []})

        monkeypatch.setattr(search, "fast_persona_classify", fake_classify)
        result = classify_persona_tool("content")
        assert seen["project"] == ("proj-x", "asia-east1")
        assert result["archetypes"] == []

    def test_persona_vector_search_refuses_without_vertex(self, monkeypatch):
        from persona.agent_tools import persona_vector_search

        monkeypatch.setattr(bare_credentials, "resolve_credentials", lambda *a: None)
        result = persona_vector_search("premium electronics buyers")
        _assert_refusal_shape(result, "vertex_ai")


# ==================== HTTP routers fail closed (409) ====================

@pytest.fixture
def client():
    from backend.persona.router import router as persona_router
    from backend.routers.brand import router as brand_router

    app = FastAPI()
    app.include_router(brand_router)
    app.include_router(persona_router)
    app.dependency_overrides[get_current_user] = lambda: _USER
    return TestClient(app)


class TestRouterGating:
    def test_brand_analyze_409_when_gemini_unconfigured(self, client, monkeypatch):
        import backend.services.credentials as backend_credentials

        monkeypatch.setattr(backend_credentials, "resolve_credentials", lambda *a: None)
        resp = client.post("/api/brand/analyze", json={"url": "https://example.com"})
        assert resp.status_code == 409
        assert "gemini" in resp.json()["detail"]

    @pytest.mark.parametrize("path,body", [
        ("/api/persona/classify", {"content": "x"}),
        ("/api/persona/classify/batch", {"contents": ["x"]}),
        ("/api/persona/analyze", {"content": "x"}),
        ("/api/persona/taxonomy/reload", {}),
    ])
    def test_persona_endpoints_409_when_vertex_unconfigured(
        self, client, monkeypatch, path, body
    ):
        import backend.services.credentials as backend_credentials

        monkeypatch.setattr(backend_credentials, "resolve_credentials", lambda *a: None)
        resp = client.post(path, json=body)
        assert resp.status_code == 409
        assert "vertex_ai" in resp.json()["detail"]

    def test_persona_classify_passes_site_project(self, client, monkeypatch):
        import backend.persona.router as persona_router_module
        import backend.services.credentials as backend_credentials

        monkeypatch.setattr(
            backend_credentials, "resolve_credentials",
            lambda site_id, service: {"project_id": "proj-y", "location": "us-east1"},
        )
        seen = {}

        def fake_classify(content, top_k, category_filter=None, project_id=None, location=None):
            seen["project"] = (project_id, location)
            return SimpleNamespace(model_dump=lambda: {"archetypes": []})

        monkeypatch.setattr(persona_router_module, "fast_persona_classify", fake_classify)
        resp = client.post("/api/persona/classify", json={"content": "x"})
        assert resp.status_code == 200
        assert seen["project"] == ("proj-y", "us-east1")


# ==================== gated_tools in the status API ====================

class TestGatedToolsStatus:
    def test_services_response_includes_gated_tools(self, monkeypatch):
        import backend.services.credentials as backend_credentials
        from backend.routers.integrations import router as integrations_router

        monkeypatch.setattr(backend_credentials, "status", lambda site_id: {})
        app = FastAPI()
        app.include_router(integrations_router)
        app.dependency_overrides[get_current_user] = lambda: _USER
        resp = TestClient(app).get("/api/integrations/services")
        assert resp.status_code == 200
        assert resp.json()["gated_tools"] == {
            "analyze_brand_tool": ["gemini"],
            "classify_persona_tool": ["vertex_ai"],
            "persona_vector_search": ["vertex_ai"],
            "persona_category_breakdown": ["vertex_ai"],
        }
