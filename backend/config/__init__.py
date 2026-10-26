"""Configuration management module for AI-CDP."""

from .loader import ConfigManager, get_config_manager
from .schemas import (
    UnifiedOntologyConfig, OntologyNode, NodeStatus,
    DataSourceNode, AttributeNode, SegmentNode,
)
from .repository import OntologyRepository, JsonOntologyRepository
from .rules_schema import RulesConfig, ComputeRule
from .rules_repository import RulesRepository, JsonRulesRepository
from .strategies_schema import StrategiesConfig, Strategy
from .strategies_repository import StrategiesRepository, JsonStrategiesRepository
from .integrity import (
    validate_rules_against_ontology, assert_rules_valid,
    validate_strategies_against_ontology, assert_strategies_valid,
    IntegrityError,
)

__all__ = [
    "ConfigManager",
    "get_config_manager",
    "UnifiedOntologyConfig",
    "OntologyNode",
    "DataSourceNode",
    "AttributeNode",
    "SegmentNode",
    "OntologyRepository",
    "JsonOntologyRepository",
    "RulesConfig",
    "ComputeRule",
    "RulesRepository",
    "JsonRulesRepository",
    "StrategiesConfig",
    "Strategy",
    "StrategiesRepository",
    "JsonStrategiesRepository",
    "validate_rules_against_ontology",
    "assert_rules_valid",
    "validate_strategies_against_ontology",
    "assert_strategies_valid",
    "IntegrityError",
]
