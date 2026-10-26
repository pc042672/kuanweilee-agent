"""Write tools for ontology nodes and compute rules (LLM-invoked mutations).

Every tool: authZ re-check at the tool boundary → validated change through
ConfigManager (the same path the HTTP routers use; integrity checks included)
→ audit row. HITL confirmation is enforced by the FunctionTool wrappers in
skills/ (per-site guardrail policy).

Tools return a diff-style dict so the agent can present the change clearly.
"""

import json
import logging
from typing import Any, Dict

from pydantic import ValidationError

from services.guardrails import audit, check_authz
from config.rules_schema import ComputeRule
from revive_agent.tools._infra import get_config

logger = logging.getLogger("ai_cdp.tools.config_write")


def _err(message: str) -> Dict[str, Any]:
    return {"success": False, "error": message}


def upsert_ontology_node_tool(node_key: str, node_json: str) -> Dict[str, Any]:
    """Create or update an ontology node (datasource/attribute/segment).

    Args:
        node_key: Unique node key, e.g. 'vip_segment'.
        node_json: Full node definition as JSON — must include 'type'
            ('datasource' | 'attribute' | 'segment') plus that type's fields.

    Returns:
        {success, action: created|updated, before, after} or {success: False, error}.
    """
    if denial := check_authz("upsert_ontology_node"):
        return _err(denial)
    try:
        node_data = json.loads(node_json)
    except json.JSONDecodeError as e:
        return _err(f"node_json is not valid JSON: {e}")

    cm = get_config()
    before = cm.get_node(node_key)
    try:
        from config.schemas import UnifiedOntologyConfig
        parsed = UnifiedOntologyConfig(nodes={node_key: node_data}).nodes[node_key]
        if before is None:
            cm.add_node(node_key, parsed)
            action = "created"
        else:
            cm.update_node(node_key, parsed)
            action = "updated"
    except (ValidationError, ValueError) as e:
        return _err(f"Validation failed: {e}")

    result = {
        "success": True,
        "action": action,
        "node_key": node_key,
        "before": before.model_dump() if before else None,
        "after": parsed.model_dump(),
    }
    audit("ontology_node_upsert", node_key, {"node": node_data}, {"action": action})
    return result


def delete_ontology_node_tool(node_key: str) -> Dict[str, Any]:
    """Delete an ontology node (refused while rules/strategies still reference it).

    Args:
        node_key: Key of the node to delete.
    """
    if denial := check_authz("delete_ontology_node"):
        return _err(denial)
    cm = get_config()
    before = cm.get_node(node_key)
    if before is None:
        return _err(f"Node '{node_key}' not found")
    refs = cm.find_node_references(node_key)
    if refs:
        return _err(f"Node '{node_key}' is still referenced by: {refs}")
    try:
        cm.delete_node(node_key)
    except ValueError as e:
        return _err(str(e))
    audit("ontology_node_delete", node_key, {}, {"deleted": True})
    return {"success": True, "action": "deleted", "node_key": node_key,
            "before": before.model_dump()}


def upsert_rule_tool(attribute_key: str, rule_json: str) -> Dict[str, Any]:
    """Create or replace the compute rule for an attribute.

    Args:
        attribute_key: Ontology AttributeNode key the rule computes.
        rule_json: ComputeRule JSON — {type: 'sql'|'quiz'|'labeling_rule',
            sources: [{datasource, column}], sql?, quiz?, valueMappings?}.
    """
    if denial := check_authz("upsert_rule"):
        return _err(denial)
    try:
        rule_data = json.loads(rule_json)
    except json.JSONDecodeError as e:
        return _err(f"rule_json is not valid JSON: {e}")
    rule_data["attribute"] = attribute_key

    cm = get_config()
    try:
        rule = ComputeRule(**rule_data)
    except ValidationError as e:
        return _err(f"Validation failed: {e}")

    rules = cm.load_rules()
    before = next((r for r in rules.computeRules if r.attribute == attribute_key), None)
    rules.computeRules = [r for r in rules.computeRules if r.attribute != attribute_key]
    rules.computeRules.append(rule)
    try:
        cm.save_rules(rules)  # runs validate_rules_against_ontology
    except ValueError as e:
        return _err(f"Integrity check failed: {e}")

    result = {
        "success": True,
        "action": "updated" if before else "created",
        "attribute": attribute_key,
        "before": before.model_dump() if before else None,
        "after": rule.model_dump(),
    }
    audit("rule_upsert", attribute_key, {"rule": rule_data}, {"action": result["action"]})
    return result


def delete_rule_tool(attribute_key: str) -> Dict[str, Any]:
    """Delete the compute rule of an attribute.

    Args:
        attribute_key: Ontology AttributeNode key whose rule is removed.
    """
    if denial := check_authz("delete_rule"):
        return _err(denial)
    cm = get_config()
    rules = cm.load_rules()
    before = next((r for r in rules.computeRules if r.attribute == attribute_key), None)
    if before is None:
        return _err(f"No compute rule found for attribute '{attribute_key}'")
    rules.computeRules = [r for r in rules.computeRules if r.attribute != attribute_key]
    cm.save_rules(rules)
    audit("rule_delete", attribute_key, {}, {"deleted": True})
    return {"success": True, "action": "deleted", "attribute": attribute_key,
            "before": before.model_dump()}
