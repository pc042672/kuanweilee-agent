"""Ontology tools — semantic sidecar (attributes, segments, strategies, scoring).

Structure comes from the ontology; behavior (compute rules + strategies) comes from
the rule/score engine config. Both are reached through ConfigManager.get_evaluator().
"""

from typing import Dict, Any, Optional

from config.scoring import ScoringError
from config.schemas import AttributeNode, SegmentNode
from config.integrity import validate_rules_against_ontology, validate_strategies_against_ontology
from revive_agent.tools._infra import get_config


def get_ontology_tool() -> Dict[str, Any]:
    """
    Returns the CDP ontology formatted for LLM understanding.
    Use this to understand what attributes, segments, and data sources exist.

    Returns:
        Dict with success status and formatted ontology prompt text.
    """
    try:
        prompt = get_config().format_ontology_for_prompt()
        return {
            "success": True,
            "ontology": prompt,
            "summary": f"Loaded ontology with formatted prompt ({len(prompt)} chars)"
        }
    except FileNotFoundError:
        return {"success": False, "error": "Ontology config (ontology.json) not found"}
    except Exception as e:
        return {"success": False, "error": f"Failed to load ontology: {e}"}


def get_attribute_tool(attribute_key: str) -> Dict[str, Any]:
    """
    Get a specific attribute by key, with its value domain (structure) and the
    compute rules (behavior) that populate it.

    Args:
        attribute_key: The node key of the attribute (e.g., 'archetype', 'purchase_power')

    Returns:
        Dict with the attribute details plus its compute rules.
    """
    try:
        cm = get_config()
        node = cm.get_node(attribute_key)
        if node is None:
            return {"success": False, "error": f"Node '{attribute_key}' not found"}
        if not isinstance(node, AttributeNode):
            return {"success": False, "error": f"Node '{attribute_key}' is type '{node.type}', not an attribute"}
        rules = [r.model_dump() for r in cm.get_compute_rules(attribute_key)]
        return {"success": True, "attribute": node.model_dump(), "compute_rules": rules}
    except Exception as e:
        return {"success": False, "error": f"Failed to get attribute: {e}"}


def score_tool(attribute_key: str, responses: Dict[str, str]) -> Dict[str, Any]:
    """
    Score responses against an attribute's quiz rule (pure: no persistence side-effect).
    Calculates primary/secondary value assignments based on scoring thresholds.

    Args:
        attribute_key: The attribute node key (e.g., 'archetype')
        responses: Dict mapping question_id to selected option_id

    Returns:
        Dict with primary results, secondary results, and all scores.
    """
    try:
        try:
            result = get_config().get_evaluator().score_quiz(attribute_key, responses)
        except ScoringError as e:
            return {"success": False, "error": str(e)}
        return {"success": True, "attribute_key": attribute_key, **result}
    except Exception as e:
        return {"success": False, "error": f"Failed to score: {e}"}


def label_scores_tool(attribute_key: str, contributions: list, scoring: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """
    Aggregate scoring signals for a category attribute and label primary/secondary.

    The engine is stateless — YOU own the running tally. Pass the FULL list of
    accumulated contributions each call. Each contribution is a source-tagged set of
    points toward category values, e.g. an initial assessment plus later signals:
        [{"source": "assessment", "points": {"explorer": 2, "sage": 1}},
         {"source": "selection",  "points": {"explorer": 1}},
         {"source": "acceptance", "points": {"explorer": 1}}]

    Args:
        attribute_key: The scored attribute node key.
        contributions: List of {"source": str, "points": {value: number}}.
        scoring: Optional threshold override {primaryThreshold, secondaryThreshold,
            maxPrimary, maxSecondary} — e.g. {"primaryThreshold": 2, "secondaryThreshold": 1}
            for a "two behavioral confirmations ⇒ primary" model. Defaults to the
            attribute's quiz thresholds.

    Returns:
        Dict with primary, secondary, all_scores.
    """
    try:
        from config.scoring import ScoreContribution
        from config.schemas import ScoringConfig
        evaluator = get_config().get_evaluator()
        contribs = [ScoreContribution(**c) for c in (contributions or [])]
        scoring_cfg = ScoringConfig(**scoring) if scoring else None
        try:
            result = evaluator.label_scores(attribute_key, contribs, scoring=scoring_cfg)
        except ScoringError as e:
            return {"success": False, "error": str(e)}
        return {"success": True, "attribute_key": attribute_key, **result}
    except Exception as e:
        return {"success": False, "error": f"Failed to label scores: {e}"}


def resolve_segments_tool(attributes: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve which segments match given user attributes (semantic sidecar).

    Args:
        attributes: Dict mapping attribute_key to value or {value, score}.

    Returns:
        Dict with matched segments, reasoning traces, configured strategies, and hints.
    """
    try:
        evaluator = get_config().get_evaluator()
        config = evaluator.ontology
        segments = {k: v for k, v in config.nodes.items() if v.type == "segment"}
        matched = []

        for seg_key, seg in segments.items():
            if not isinstance(seg, SegmentNode):
                continue
            is_match, reasoning = evaluator.evaluate_segment(seg_key, attributes)
            if is_match:
                matched.append({
                    "key": seg_key,
                    "name": seg.name,
                    "description": seg.description,
                    "reasoning": reasoning,
                    "strategies": [s.key for s in evaluator.strategies_for(seg_key)],
                    "execution_hints": {
                        "attributes_referenced": [c.attribute for c in seg.conditions],
                    },
                })

        return {
            "success": True,
            "site_id": config.site_id,
            "ontology_version": config.version,
            "matched": matched,
            "total_segments_evaluated": len(segments),
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to resolve segments: {e}"}


def resolve_strategy_tool(
    segment_key: str, strategy_key: str, context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Resolve a configured strategy for a segment. Generalizes NBA/NBO: pass
    strategy_key="nba", "nbo", or any custom strategy configured on the segment.

    Args:
        segment_key: The segment node key (e.g., 'explorer_campaign')
        strategy_key: The strategy key (e.g., 'nba', 'nbo', 'next_channel')
        context: Optional values to fill the strategy template (e.g., {"offering": "..."})

    Returns:
        Dict with the resolved strategy (template, rendered message, params) and taxonomy context.
    """
    try:
        evaluator = get_config().get_evaluator()
        node = evaluator.ontology.nodes.get(segment_key)
        if node is None:
            return {"success": False, "error": f"Segment '{segment_key}' not found"}
        if not isinstance(node, SegmentNode):
            return {"success": False, "error": f"Node '{segment_key}' is not a segment"}
        try:
            resolved = evaluator.resolve_strategy(segment_key, strategy_key, context)
        except ScoringError as e:
            return {"success": False, "error": str(e)}

        return {
            "success": True,
            "segment_name": node.name,
            **resolved,
            "taxonomy_context": evaluator.build_taxonomy_context(segment_key),
            "execution_hints": {
                "sources_used": [c.attribute for c in node.conditions],
            },
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to resolve strategy: {e}"}


def audit_ontology_tool() -> Dict[str, Any]:
    """
    Audit the ontology + rule config for integrity issues. Checks for:
    - Segment conditions referencing non-existent attributes
    - Compute rules / strategies referencing non-existent ontology entities

    Returns:
        Dict with audit results and any issues found.
    """
    try:
        cm = get_config()
        config = cm.load_ontology()
        rules = cm.load_rules()
        strategies = cm.load_strategies()
        issues = []
        stats = {"total_nodes": len(config.nodes), "by_type": {}}
        for node in config.nodes.values():
            stats["by_type"][node.type] = stats["by_type"].get(node.type, 0) + 1

        for key, node in config.nodes.items():
            if isinstance(node, SegmentNode):
                for cond in node.conditions:
                    if cond.attribute not in config.nodes:
                        issues.append(f"ORPHAN: segment '{key}' references missing attribute '{cond.attribute}'")

        issues.extend(validate_rules_against_ontology(rules, config))
        issues.extend(validate_strategies_against_ontology(strategies, config))

        return {
            "success": True,
            "stats": stats,
            "issues": issues,
            "healthy": len(issues) == 0,
        }
    except FileNotFoundError:
        return {"success": False, "error": "Ontology config (ontology.json) not found"}
    except Exception as e:
        return {"success": False, "error": f"Failed to audit ontology: {e}"}
