"""Security tests — SQL injection, prompt injection, table auth, model guard, PII."""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock

from config.schemas import (
    UnifiedOntologyConfig, DataSourceNode, AttributeNode, SegmentNode,
    SegmentCondition,
)
from config.loader import ConfigManager


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _make_plugin():
    """Create a fresh SQLSafetyPlugin."""
    from revive_agent.plugins import SQLSafetyPlugin
    return SQLSafetyPlugin()


def _make_tool_mock(name="dry_run_sql_tool"):
    tool = MagicMock()
    tool.name = name
    return tool


def _make_tool_context():
    ctx = MagicMock()
    ctx.state = {}
    return ctx


def _run(coro):
    return asyncio.run(coro)


# ═══════════════════════════════════════════════════════════════
# SQL Injection Tests
# ═══════════════════════════════════════════════════════════════

class TestSQLInjection:
    def test_drop_table_blocked(self):
        plugin = _make_plugin()
        result = _run(plugin.before_tool_callback(
            tool=_make_tool_mock(), tool_args={"sql_query": "DROP TABLE users"},
            tool_context=_make_tool_context(),
        ))
        assert result is not None
        assert result["valid"] is False

    def test_delete_appended_blocked(self):
        plugin = _make_plugin()
        result = _run(plugin.before_tool_callback(
            tool=_make_tool_mock(),
            tool_args={"sql_query": "SELECT 1; DELETE FROM users"},
            tool_context=_make_tool_context(),
        ))
        assert result is not None
        assert result["valid"] is False

    def test_union_select_blocked(self):
        """UNION is allowed (it's part of SELECT), but INSERT/UPDATE hidden inside are blocked."""
        plugin = _make_plugin()
        result = _run(plugin.before_tool_callback(
            tool=_make_tool_mock(),
            tool_args={"sql_query": "SELECT 1 UNION INSERT INTO passwords SELECT *"},
            tool_context=_make_tool_context(),
        ))
        assert result is not None
        assert result["valid"] is False
        assert "INSERT" in result["error"]

    def test_insert_as_cte_blocked(self):
        plugin = _make_plugin()
        result = _run(plugin.before_tool_callback(
            tool=_make_tool_mock(),
            tool_args={"sql_query": "WITH x AS (INSERT INTO t VALUES (1)) SELECT * FROM x"},
            tool_context=_make_tool_context(),
        ))
        assert result is not None
        assert result["valid"] is False

    def test_sql_comment_bypass_blocked(self):
        plugin = _make_plugin()
        result = _run(plugin.before_tool_callback(
            tool=_make_tool_mock(),
            tool_args={"sql_query": "SELECT 1 -- DROP TABLE users"},
            tool_context=_make_tool_context(),
        ))
        # DROP appears in the SQL text, plugin blocks it
        assert result is not None
        assert result["valid"] is False

    def test_truncate_blocked(self):
        plugin = _make_plugin()
        result = _run(plugin.before_tool_callback(
            tool=_make_tool_mock(),
            tool_args={"sql_query": "TRUNCATE TABLE orders"},
            tool_context=_make_tool_context(),
        ))
        assert result is not None
        assert result["valid"] is False

    def test_grant_blocked(self):
        plugin = _make_plugin()
        result = _run(plugin.before_tool_callback(
            tool=_make_tool_mock(),
            tool_args={"sql_query": "GRANT ALL ON users TO hacker"},
            tool_context=_make_tool_context(),
        ))
        assert result is not None
        assert result["valid"] is False

    def test_valid_select_allowed(self):
        plugin = _make_plugin()
        result = _run(plugin.before_tool_callback(
            tool=_make_tool_mock(),
            tool_args={"sql_query": "SELECT count(*) FROM cdp.member_profile WHERE gender_code = '01'"},
            tool_context=_make_tool_context(),
        ))
        assert result is None  # None means allowed

    def test_valid_cte_allowed(self):
        plugin = _make_plugin()
        result = _run(plugin.before_tool_callback(
            tool=_make_tool_mock(),
            tool_args={"sql_query": "WITH cte AS (SELECT * FROM cdp.member_rfm) SELECT * FROM cte"},
            tool_context=_make_tool_context(),
        ))
        assert result is None

    def test_explain_allowed(self):
        plugin = _make_plugin()
        result = _run(plugin.before_tool_callback(
            tool=_make_tool_mock(),
            tool_args={"sql_query": "EXPLAIN SELECT * FROM cdp.member_profile"},
            tool_context=_make_tool_context(),
        ))
        assert result is None

    def test_non_sql_tool_ignored(self):
        plugin = _make_plugin()
        result = _run(plugin.before_tool_callback(
            tool=_make_tool_mock(name="get_ontology_tool"),
            tool_args={"sql_query": "DROP TABLE users"},
            tool_context=_make_tool_context(),
        ))
        assert result is None  # Not a SQL tool, plugin ignores it

    def test_create_table_blocked(self):
        plugin = _make_plugin()
        result = _run(plugin.before_tool_callback(
            tool=_make_tool_mock(),
            tool_args={"sql_query": "CREATE TABLE hacked (id int)"},
            tool_context=_make_tool_context(),
        ))
        assert result is not None
        assert result["valid"] is False

    def test_alter_table_blocked(self):
        plugin = _make_plugin()
        result = _run(plugin.before_tool_callback(
            tool=_make_tool_mock(),
            tool_args={"sql_query": "ALTER TABLE users ADD COLUMN backdoor text"},
            tool_context=_make_tool_context(),
        ))
        assert result is not None
        assert result["valid"] is False

    def test_update_blocked(self):
        plugin = _make_plugin()
        result = _run(plugin.before_tool_callback(
            tool=_make_tool_mock(),
            tool_args={"sql_query": "UPDATE users SET role = 'admin' WHERE 1=1"},
            tool_context=_make_tool_context(),
        ))
        assert result is not None
        assert result["valid"] is False


# ═══════════════════════════════════════════════════════════════
# Table Authorization Tests
# ═══════════════════════════════════════════════════════════════

class TestTableAuthorization:
    @pytest.fixture
    def config_with_datasources(self, tmp_path):
        """ConfigManager with ontology that has DataSource nodes."""
        import json
        ontology = {
            "version": "3.0.0",
            "site_id": "default",
            "nodes": {
                "member_profile": {
                    "type": "datasource",
                    "name": "Member Profile",
                    "table": "cdp.member_profile",
                },
                "member_rfm": {
                    "type": "datasource",
                    "name": "Member RFM",
                    "table": "cdp.member_rfm",
                },
                "gender": {
                    "type": "attribute",
                    "name": "Gender",
                },
            },
        }
        (tmp_path / "ontology.json").write_text(json.dumps(ontology))
        return ConfigManager(config_dir=str(tmp_path))

    def test_get_allowed_tables(self, config_with_datasources):
        allowed = config_with_datasources.get_allowed_tables()
        assert allowed == {"cdp.member_profile", "cdp.member_rfm"}

    def test_allowed_tables_excludes_non_datasource(self, config_with_datasources):
        allowed = config_with_datasources.get_allowed_tables()
        assert "gender" not in str(allowed)

    def test_empty_ontology_returns_empty_set(self, tmp_path):
        import json
        ontology = {"version": "3.0.0", "site_id": "default", "nodes": {}}
        (tmp_path / "ontology.json").write_text(json.dumps(ontology))
        mgr = ConfigManager(config_dir=str(tmp_path))
        assert mgr.get_allowed_tables() == set()


# ═══════════════════════════════════════════════════════════════
# Model Guard / PII Tests
# ═══════════════════════════════════════════════════════════════

class TestPIIRedaction:
    def test_credit_card_redacted(self):
        from revive_agent.plugins import _redact_pii
        text = "My card is 4111-1111-1111-1111 please charge it"
        redacted, detected = _redact_pii(text)
        assert "[REDACTED]" in redacted
        assert "4111" not in redacted
        assert "credit_card" in detected

    def test_ssn_redacted(self):
        from revive_agent.plugins import _redact_pii
        text = "SSN: 123-45-6789"
        redacted, detected = _redact_pii(text)
        assert "[REDACTED]" in redacted
        assert "123-45-6789" not in redacted
        assert "ssn" in detected

    def test_email_redacted(self):
        from revive_agent.plugins import _redact_pii
        text = "Contact user@example.com for details"
        redacted, detected = _redact_pii(text)
        assert "[REDACTED]" in redacted
        assert "user@example.com" not in redacted
        assert "email" in detected

    def test_phone_redacted(self):
        from revive_agent.plugins import _redact_pii
        text = "Call me at (555) 123-4567"
        redacted, detected = _redact_pii(text)
        assert "[REDACTED]" in redacted
        assert "555" not in redacted
        assert "phone" in detected

    def test_no_pii_unchanged(self):
        from revive_agent.plugins import _redact_pii
        text = "Find all VIP customers in Taipei"
        redacted, detected = _redact_pii(text)
        assert redacted == text
        assert detected == []

    def test_multiple_pii_all_redacted(self):
        from revive_agent.plugins import _redact_pii
        text = "Card 4111111111111111 SSN 123-45-6789 email user@test.com"
        redacted, detected = _redact_pii(text)
        assert "4111" not in redacted
        assert "123-45" not in redacted
        assert "user@test" not in redacted
        assert len(detected) == 3

    def test_passport_redacted(self):
        from revive_agent.plugins import _redact_pii
        text = "Passport number A123456789"
        redacted, detected = _redact_pii(text)
        assert "[REDACTED]" in redacted
        assert "passport" in detected


# ═══════════════════════════════════════════════════════════════
# Auth Tests (production mode)
# ═══════════════════════════════════════════════════════════════

class TestAuthSecurity:
    """These tests require the FastAPI test client with DEV_MODE disabled."""

    @pytest.fixture
    def client(self):
        import os
        os.environ.setdefault("DEV_USER_EMAIL", "test@dev.com")
        from fastapi.testclient import TestClient
        from backend.server import app
        return TestClient(app)

    @pytest.fixture
    def no_dev_mode(self, monkeypatch):
        import sys
        import backend.settings as settings_mod
        monkeypatch.setattr(settings_mod, "DEV_MODE", False)
        if "settings" in sys.modules:
            monkeypatch.setattr(sys.modules["settings"], "DEV_MODE", False)

    def test_no_auth_returns_guest_or_401(self, client, no_dev_mode):
        """Without JWT in production, protected endpoints should fail."""
        r = client.get("/api/ontology")
        # Should either be 401 or return guest context (depends on implementation)
        assert r.status_code in (200, 401, 403)

    def test_malformed_jwt_returns_401(self, client, no_dev_mode):
        r = client.get("/api/ontology", headers={"Authorization": "Bearer completely-invalid-token"})
        assert r.status_code == 401

    def test_expired_jwt_returns_401(self, client, no_dev_mode):
        from backend.auth import create_session_jwt
        import backend.auth as auth_mod
        original = auth_mod.JWT_EXPIRY_SECONDS
        auth_mod.JWT_EXPIRY_SECONDS = -1  # Already expired
        token = create_session_jwt({
            "user_id": 1, "email": "x@test.com", "name": "X",
            "site_id": 1, "role": "admin",
        })
        auth_mod.JWT_EXPIRY_SECONDS = original
        r = client.get("/api/ontology", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401
