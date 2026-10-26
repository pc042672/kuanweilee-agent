"""Tests for config write tools — authZ, integrity, guardrail policy."""

import json

import pytest

from backend.config.loader import ConfigManager


@pytest.fixture(autouse=True)
def json_config(tmp_path, monkeypatch):
    """Point ConfigManager at a temp copy of the shipped config dir."""
    import shutil
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "config"
    for name in ["ontology.json", "rules.json", "strategies.json"]:
        shutil.copy(src / name, tmp_path / name)

    monkeypatch.delenv("DATABASE_URL", raising=False)
    ConfigManager.reset_instance()
    cm = ConfigManager.get_instance(config_dir=str(tmp_path))
    # Write tools resolve config via _infra.get_config (site-aware); point it at
    # the temp manager for the test.
    import backend.revive_agent.tools.config_write_tools as cwt
    monkeypatch.setattr(cwt, "get_config", lambda: cm)
    yield cm
    ConfigManager.reset_instance()


def test_upsert_node_authz_denied_for_member(monkeypatch):
    import services.guardrails as g
    from backend.auth import UserContext
    monkeypatch.setattr(g, "current_user",
                        lambda: UserContext(user_id=1, email="m@x.com", name="M",
                                            site_id=1, role="member"))
    from backend.revive_agent.tools.config_write_tools import upsert_ontology_node_tool
    res = upsert_ontology_node_tool("x_attr", '{"type":"attribute","name":"X"}')
    assert res["success"] is False
    assert "authorized" in res["error"].lower()


def test_upsert_node_valid(monkeypatch, json_config):
    _admin(monkeypatch)
    from backend.revive_agent.tools.config_write_tools import upsert_ontology_node_tool
    res = upsert_ontology_node_tool(
        "test_attr", '{"type":"attribute","name":"Test Attr","valueType":"STR"}')
    assert res["success"] is True
    assert res["action"] == "created"
    assert json_config.get_node("test_attr") is not None


def test_upsert_node_invalid_rejected(monkeypatch):
    _admin(monkeypatch)
    from backend.revive_agent.tools.config_write_tools import upsert_ontology_node_tool
    res = upsert_ontology_node_tool("bad", '{"type":"attribute"}')  # missing name
    assert res["success"] is False
    assert "Validation failed" in res["error"]


def test_upsert_rule_integrity_rejects_unknown_attribute(monkeypatch):
    _admin(monkeypatch)
    from backend.revive_agent.tools.config_write_tools import upsert_rule_tool
    res = upsert_rule_tool(
        "no_such_attribute",
        json.dumps({"type": "sql", "sql": "SELECT 1", "sources": []}))
    assert res["success"] is False
    assert "Integrity" in res["error"] or "Validation" in res["error"]


def test_delete_node_blocked_by_references(monkeypatch, json_config):
    _admin(monkeypatch)
    from backend.revive_agent.tools.config_write_tools import delete_ontology_node_tool
    # 'archetype' is referenced by segment conditions + rules
    res = delete_ontology_node_tool("archetype")
    assert res["success"] is False
    assert "referenced" in res["error"].lower()


def test_guardrail_levels(monkeypatch):
    import services.guardrails as g
    from services.guardrails import DESTRUCTIVE, MUTATING, needs_confirmation

    monkeypatch.setattr(g, "guardrail_level", lambda site_id=None: "strict")
    assert needs_confirmation(MUTATING)() is True
    assert needs_confirmation(DESTRUCTIVE)() is True

    monkeypatch.setattr(g, "guardrail_level", lambda site_id=None: "standard")
    assert needs_confirmation(MUTATING)() is False
    assert needs_confirmation(DESTRUCTIVE)() is True

    monkeypatch.setattr(g, "guardrail_level", lambda site_id=None: "trusted")
    assert needs_confirmation(MUTATING)() is False
    assert needs_confirmation(DESTRUCTIVE)() is False


def _admin(monkeypatch):
    import services.guardrails as g
    from backend.auth import UserContext
    monkeypatch.setattr(g, "current_user",
                        lambda: UserContext(user_id=1, email="a@x.com", name="A",
                                            site_id=1, role="admin"))
