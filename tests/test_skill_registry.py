"""Tests for the skill registry and executor skills."""

import json


def test_registry_lists_enabled_skills():
    from skills.registry import SKILLS, list_skills

    names = {s["name"] for s in list_skills()}
    assert {"sql_execution", "audience_export", "chart_generation",
            "execute_action", "get_taxonomy", "list_campaigns"} <= names
    # python_analysis is gated off by default
    assert "python_analysis" not in names
    assert "python_analysis" not in SKILLS


def test_chart_generation_shape():
    from revive_agent.tools.skill_exec_tools import chart_generation_tool

    data = json.dumps([
        {"archetype": "hero", "count": 12},
        {"archetype": "sage", "count": 7},
    ])
    res = chart_generation_tool("bar", "Archetype counts", data, "archetype", "count")
    assert res["success"] is True
    assert res["chart"]["type"] == "bar"
    assert res["chart"]["x"] == "archetype"
    assert len(res["chart"]["data"]) == 2


def test_chart_generation_rejects_unknown_type():
    from revive_agent.tools.skill_exec_tools import chart_generation_tool

    res = chart_generation_tool("pie3d", "t", "[{}]", "x", "y")
    assert res["success"] is False


def test_chart_generation_rejects_missing_field():
    from revive_agent.tools.skill_exec_tools import chart_generation_tool

    data = json.dumps([{"a": 1}])
    res = chart_generation_tool("bar", "t", data, "missing_x", "a")
    assert res["success"] is False
    assert "missing_x" in res["error"]


def test_python_skill_gated_off():
    from revive_agent.tools.skill_exec_tools import python_analysis_tool

    res = python_analysis_tool("print(1)")
    assert res["success"] is False
    assert "PYTHON_SKILL_ENABLED" in res["error"]
