"""Tests for referential integrity of rules.json + strategies.json against the ontology."""

import pytest

from config.schemas import (
    UnifiedOntologyConfig, AttributeNode, SegmentNode, DataSourceNode, SourceRef,
)
from config.rules_schema import RulesConfig, ComputeRule
from config.strategies_schema import StrategiesConfig, Strategy
from config.integrity import (
    validate_rules_against_ontology, assert_rules_valid,
    validate_strategies_against_ontology, assert_strategies_valid, IntegrityError,
)


@pytest.fixture
def ontology():
    return UnifiedOntologyConfig(nodes={
        "members": DataSourceNode(name="Members", table="cdp.members"),
        "archetype": AttributeNode(name="Archetype"),
        "explorer_campaign": SegmentNode(name="Explorer Campaign"),
    })


def test_valid_rules_pass(ontology):
    rules = RulesConfig(
        computeRules=[ComputeRule(attribute="archetype", type="sql", sql="SELECT 1",
                                  sources=[SourceRef(datasource="members", column="id")])],
    )
    strategies = StrategiesConfig(strategies=[Strategy(key="nba", segment="explorer_campaign")])
    assert validate_rules_against_ontology(rules, ontology) == []
    assert validate_strategies_against_ontology(strategies, ontology) == []
    assert_rules_valid(rules, ontology)  # no raise
    assert_strategies_valid(strategies, ontology)  # no raise


def test_compute_rule_unknown_attribute(ontology):
    rules = RulesConfig(computeRules=[ComputeRule(attribute="ghost", type="sql", sql="")])
    errors = validate_rules_against_ontology(rules, ontology)
    assert any("unknown attribute 'ghost'" in e for e in errors)
    with pytest.raises(IntegrityError):
        assert_rules_valid(rules, ontology)


def test_compute_rule_unknown_datasource(ontology):
    rules = RulesConfig(computeRules=[
        ComputeRule(attribute="archetype", type="sql", sql="", sources=[SourceRef(datasource="ghost", column="x")]),
    ])
    errors = validate_rules_against_ontology(rules, ontology)
    assert any("unknown datasource 'ghost'" in e for e in errors)


def test_strategy_unknown_segment(ontology):
    strategies = StrategiesConfig(strategies=[Strategy(key="nba", segment="ghost")])
    errors = validate_strategies_against_ontology(strategies, ontology)
    assert any("unknown segment 'ghost'" in e for e in errors)
    with pytest.raises(IntegrityError):
        assert_strategies_valid(strategies, ontology)


def test_strategy_segment_must_be_segment_node(ontology):
    strategies = StrategiesConfig(strategies=[Strategy(key="nba", segment="archetype")])
    errors = validate_strategies_against_ontology(strategies, ontology)
    assert any("is not a segment node" in e for e in errors)


def test_attribute_fk_must_be_attribute_node(ontology):
    # referencing a datasource key where an attribute is expected
    rules = RulesConfig(computeRules=[ComputeRule(attribute="members", type="sql", sql="")])
    errors = validate_rules_against_ontology(rules, ontology)
    assert any("is not an attribute node" in e for e in errors)
