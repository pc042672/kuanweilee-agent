"""Referential integrity between the rule/score engine config and the ontology.

Enforces the SWRL-on-OWL discipline that keeps the two-config split drift-free:
every rule references ontology entities BY KEY and those keys must resolve to a
node of the right type. Run on load and save of the behavior config.
"""

from typing import List

from .schemas import UnifiedOntologyConfig, AttributeNode, SegmentNode, DataSourceNode
from .rules_schema import RulesConfig
from .strategies_schema import StrategiesConfig


class IntegrityError(ValueError):
    """Raised when a rule/strategy references an ontology entity that does not exist."""


def validate_rules_against_ontology(
    rules: RulesConfig, ontology: UnifiedOntologyConfig
) -> List[str]:
    """Return a list of compute-rule integrity errors (empty list = valid)."""
    errors: List[str] = []
    nodes = ontology.nodes

    for cr in rules.computeRules:
        node = nodes.get(cr.attribute)
        if node is None:
            errors.append(f"ComputeRule references unknown attribute '{cr.attribute}'")
        elif not isinstance(node, AttributeNode):
            errors.append(f"ComputeRule.attribute '{cr.attribute}' is not an attribute node")
        for src in cr.sources:
            ds = nodes.get(src.datasource)
            if ds is None:
                errors.append(
                    f"ComputeRule '{cr.attribute}' references unknown datasource '{src.datasource}'"
                )
            elif not isinstance(ds, DataSourceNode):
                errors.append(
                    f"ComputeRule '{cr.attribute}' source '{src.datasource}' is not a datasource node"
                )
    return errors


def validate_strategies_against_ontology(
    strategies: StrategiesConfig, ontology: UnifiedOntologyConfig
) -> List[str]:
    """Return a list of strategy integrity errors (empty list = valid)."""
    errors: List[str] = []
    nodes = ontology.nodes
    for st in strategies.strategies:
        node = nodes.get(st.segment)
        if node is None:
            errors.append(f"Strategy '{st.key}' references unknown segment '{st.segment}'")
        elif not isinstance(node, SegmentNode):
            errors.append(f"Strategy '{st.key}' segment '{st.segment}' is not a segment node")
    return errors


def assert_rules_valid(rules: RulesConfig, ontology: UnifiedOntologyConfig) -> None:
    """Raise IntegrityError if any compute rule references a missing/mistyped entity."""
    errors = validate_rules_against_ontology(rules, ontology)
    if errors:
        raise IntegrityError("Rule/ontology integrity errors: " + "; ".join(errors))


def assert_strategies_valid(strategies: StrategiesConfig, ontology: UnifiedOntologyConfig) -> None:
    """Raise IntegrityError if any strategy references a missing/mistyped segment."""
    errors = validate_strategies_against_ontology(strategies, ontology)
    if errors:
        raise IntegrityError("Strategy/ontology integrity errors: " + "; ".join(errors))
