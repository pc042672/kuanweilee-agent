"""Configuration loader — unified v3 ontology."""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from .schemas import (
    UnifiedOntologyConfig, OntologyNode,
    DataSourceNode, AttributeNode, SegmentNode,
    TaxonomyOptionConfig,
)
from .repository import JsonOntologyRepository, OntologyRepository
from .rules_schema import RulesConfig, ComputeRule
from .rules_repository import JsonRulesRepository, RulesRepository
from .strategies_schema import StrategiesConfig, Strategy
from .strategies_repository import JsonStrategiesRepository, StrategiesRepository
from .integrity import assert_rules_valid, assert_strategies_valid


def _find_project_root() -> Path:
    """Find the project root directory by looking for marker files."""
    current = Path(__file__).resolve().parent
    for _ in range(5):
        if (current / ".git").exists():
            return current
        if (current / "pyproject.toml").exists():
            return current
        if (current / "config" / "ontology.json").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent.parent.parent


class ConfigManager:
    """Singleton manager for loading and caching the unified ontology config."""

    _instance: Optional["ConfigManager"] = None

    def __init__(self, config_dir: Optional[str] = None):
        if config_dir:
            self.config_dir = Path(config_dir)
        elif os.getenv("CONFIG_DIR"):
            self.config_dir = Path(os.getenv("CONFIG_DIR"))
        else:
            project_root = _find_project_root()
            self.config_dir = project_root / "config"

        self._ontology_repo: OntologyRepository = self._create_ontology_repo()
        self._rules_repo: RulesRepository = self._create_rules_repo()
        self._strategies_repo: StrategiesRepository = self._create_strategies_repo()
        self._ontology: Optional[UnifiedOntologyConfig] = None
        self._rules: Optional[RulesConfig] = None
        self._strategies: Optional[StrategiesConfig] = None
        self._evaluator = None
        self._allowed_tables: Optional[set] = None

    def _create_ontology_repo(self) -> "OntologyRepository":
        """Pick database repo if DATABASE_URL is set, else JSON files."""
        try:
            from db import get_engine
            engine = get_engine()
            if engine is not None:
                from .db_repository import DbOntologyRepository
                return DbOntologyRepository(engine)
        except ImportError:
            pass
        return JsonOntologyRepository(self.config_dir)

    def _create_rules_repo(self) -> "RulesRepository":
        """Pick database rules repo if DATABASE_URL is set, else JSON files."""
        try:
            from db import get_engine
            engine = get_engine()
            if engine is not None:
                from .rules_repository import DbRulesRepository
                return DbRulesRepository(engine)
        except ImportError:
            pass
        return JsonRulesRepository(self.config_dir)

    def _create_strategies_repo(self) -> "StrategiesRepository":
        """Pick database strategies repo if DATABASE_URL is set, else JSON files."""
        try:
            from db import get_engine
            engine = get_engine()
            if engine is not None:
                from .strategies_repository import DbStrategiesRepository
                return DbStrategiesRepository(engine)
        except ImportError:
            pass
        return JsonStrategiesRepository(self.config_dir)

    @classmethod
    def get_instance(cls, config_dir: Optional[str] = None) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = cls(config_dir)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def load_ontology(self, site_id: str = "default") -> UnifiedOntologyConfig:
        """Load the unified ontology config (cached)."""
        if self._ontology is None:
            self._ontology = self._ontology_repo.load(site_id)
        return self._ontology

    def save_ontology(self, config: UnifiedOntologyConfig, site_id: str = "default") -> None:
        """Persist ontology config via the repository."""
        self._ontology_repo.save(config, site_id)
        self._ontology = config
        self._evaluator = None
        self._allowed_tables = None

    def reload(self) -> None:
        """Force reload (load-then-swap for atomicity)."""
        new_ontology = None
        try:
            new_ontology = self._ontology_repo.load()
        except FileNotFoundError:
            pass
        self._ontology = new_ontology
        self._rules = None
        self._strategies = None
        self._evaluator = None
        self._allowed_tables = None

    # ── Rule/score engine config (behavior layer) ──────────────────────────

    def load_rules(self, site_id: str = "default") -> RulesConfig:
        """Load the behavior config (cached). Returns an empty config if none exists
        so the app boots on an ontology-only deployment."""
        if self._rules is None:
            try:
                self._rules = self._rules_repo.load(site_id)
            except FileNotFoundError:
                self._rules = RulesConfig(site_id=site_id)
        return self._rules

    def save_rules(self, config: RulesConfig, site_id: str = "default") -> None:
        """Persist behavior config after validating it against the ontology."""
        assert_rules_valid(config, self.load_ontology(site_id))
        self._rules_repo.save(config, site_id)
        self._rules = config
        self._evaluator = None

    def get_compute_rules(self, attribute_key: str, site_id: str = "default") -> List[ComputeRule]:
        """All compute rules whose `attribute` FK matches the given key."""
        return [r for r in self.load_rules(site_id).computeRules if r.attribute == attribute_key]

    # ── Strategy config (action layer) ─────────────────────────────────────

    def load_strategies(self, site_id: str = "default") -> StrategiesConfig:
        """Load the strategy config (cached). Returns an empty config if none exists."""
        if self._strategies is None:
            try:
                self._strategies = self._strategies_repo.load(site_id)
            except FileNotFoundError:
                self._strategies = StrategiesConfig(site_id=site_id)
        return self._strategies

    def save_strategies(self, config: StrategiesConfig, site_id: str = "default") -> None:
        """Persist strategy config after validating it against the ontology."""
        assert_strategies_valid(config, self.load_ontology(site_id))
        self._strategies_repo.save(config, site_id)
        self._strategies = config
        self._evaluator = None

    def get_strategies(self, segment_key: str, site_id: str = "default") -> List[Strategy]:
        """All strategies whose `segment` FK matches the given key."""
        return [s for s in self.load_strategies(site_id).strategies if s.segment == segment_key]

    def get_evaluator(self, site_id: str = "default"):
        """An OntologyEvaluator bound to this site's ontology + rules + strategies (cached;
        invalidated whenever any config is saved or reloaded)."""
        if self._evaluator is None:
            from .scoring import OntologyEvaluator
            self._evaluator = OntologyEvaluator(
                self.load_ontology(site_id), self.load_rules(site_id), self.load_strategies(site_id)
            )
        return self._evaluator

    def get_allowed_tables(self, site_id: str = "default") -> set:
        """Return cached set of table names from DataSource nodes (the table allowlist)."""
        if self._allowed_tables is None:
            config = self.load_ontology(site_id)
            self._allowed_tables = {n.table for n in config.nodes.values() if isinstance(n, DataSourceNode)}
        return self._allowed_tables

    def get_nodes(self, node_type: Optional[str] = None, site_id: str = "default") -> Dict[str, OntologyNode]:
        """Get ontology nodes, optionally filtered by type."""
        config = self.load_ontology(site_id)
        if node_type:
            return {k: v for k, v in config.nodes.items() if v.type == node_type}
        return config.nodes

    def get_node(self, key: str, site_id: str = "default") -> Optional[OntologyNode]:
        """Get a single ontology node by key."""
        config = self.load_ontology(site_id)
        return config.nodes.get(key)

    def add_node(self, key: str, node: OntologyNode, site_id: str = "default") -> None:
        """Add a new ontology node with validation."""
        config = self.load_ontology(site_id)
        if key in config.nodes:
            raise ValueError(f"Node '{key}' already exists")
        self._validate_node_refs(node, config, key)
        config.nodes[key] = node
        self.save_ontology(config, site_id)

    def update_node(self, key: str, node: OntologyNode, site_id: str = "default") -> None:
        """Update an existing ontology node."""
        config = self.load_ontology(site_id)
        if key not in config.nodes:
            raise ValueError(f"Node '{key}' not found")
        self._validate_node_refs(node, config, key)
        config.nodes[key] = node
        self.save_ontology(config, site_id)

    def delete_node(self, key: str, site_id: str = "default") -> None:
        """Delete an ontology node with cascade protection."""
        config = self.load_ontology(site_id)
        if key not in config.nodes:
            raise ValueError(f"Node '{key}' not found")
        referencing = self._find_referencing_nodes(key, config)
        if referencing:
            raise ValueError(f"Cannot delete node '{key}': referenced by {', '.join(referencing)}")
        del config.nodes[key]
        self.save_ontology(config, site_id)

    def _validate_node_refs(self, node: OntologyNode, config: UnifiedOntologyConfig, key: str) -> None:
        """Validate that segment conditions reference existing attributes."""
        if isinstance(node, SegmentNode):
            for cond in node.conditions:
                if cond.attribute not in config.nodes and cond.attribute != key:
                    raise ValueError(f"Segment condition references unknown attribute '{cond.attribute}'")

    def _find_referencing_nodes(self, key: str, config: UnifiedOntologyConfig) -> List[str]:
        """Find all nodes that reference a given key (flat list for error messages)."""
        refs = self.find_node_references(key, config.site_id)
        return [f"'{k}' (segment)" for k in refs["conditions"]] + \
               [f"'{k}' (attribute)" for k in refs["sources"]]

    def add_node_option(self, node_key: str, option: TaxonomyOptionConfig, site_id: str = "default") -> None:
        """Add an option to an attribute node."""
        config = self.load_ontology(site_id)
        node = config.nodes.get(node_key)
        if not node:
            raise ValueError(f"Node '{node_key}' not found")
        if node.type != "attribute":
            raise ValueError(f"Node '{node_key}' is not an attribute type")
        for opt in node.options:
            if opt.value == option.value:
                raise ValueError(f"Option value '{option.value}' already exists in node '{node_key}'")
        node.options.append(option)
        self.save_ontology(config, site_id)

    def delete_node_option(self, node_key: str, value: str, site_id: str = "default") -> None:
        """Remove an option from an attribute node by value."""
        config = self.load_ontology(site_id)
        node = config.nodes.get(node_key)
        if not node:
            raise ValueError(f"Node '{node_key}' not found")
        if node.type != "attribute":
            raise ValueError(f"Node '{node_key}' is not an attribute type")
        original_len = len(node.options)
        node.options = [o for o in node.options if o.value != value]
        if len(node.options) == original_len:
            raise ValueError(f"Option value '{value}' not found in node '{node_key}'")
        self.save_ontology(config, site_id)

    def find_node_references(self, key: str, site_id: str = "default") -> Dict[str, List[str]]:
        """Find what references a node: segments via conditions (ontology) and
        attributes via compute-rule sources (behavior config)."""
        config = self.load_ontology(site_id)
        refs: Dict[str, List[str]] = {"conditions": [], "sources": []}
        for k, n in config.nodes.items():
            if k == key:
                continue
            if isinstance(n, SegmentNode):
                for cond in n.conditions:
                    if cond.attribute == key:
                        refs["conditions"].append(k)
                        break
        for rule in self.load_rules(site_id).computeRules:
            if any(src.datasource == key for src in rule.sources):
                if rule.attribute not in refs["sources"]:
                    refs["sources"].append(rule.attribute)
        return refs

    def format_ontology_for_prompt(self, site_id: str = "default") -> str:
        """Format ontology nodes as a prompt-friendly string for LLM context.

        Joins structure (ontology) with behavior (compute rules + strategies) so the
        LLM sees how attributes are computed and what strategies a segment carries —
        the discoverability the two-config split would otherwise scatter.
        """
        config = self.load_ontology(site_id)
        rules = self.load_rules(site_id)
        strategies = self.load_strategies(site_id)
        lines = ["## CDP Ontology", ""]

        rules_by_attr: Dict[str, List] = {}
        for r in rules.computeRules:
            rules_by_attr.setdefault(r.attribute, []).append(r)
        strategies_by_segment: Dict[str, List] = {}
        for s in strategies.strategies:
            strategies_by_segment.setdefault(s.segment, []).append(s)

        by_type: Dict[str, Dict[str, OntologyNode]] = {}
        for key, node in config.nodes.items():
            if node.status != "active":
                continue
            by_type.setdefault(node.type, {})[key] = node

        for node_type, nodes in by_type.items():
            lines.append(f"### {node_type}")
            lines.append("")

            for key, node in nodes.items():
                lines.append(f"**{node.name}** (`{key}`)")
                if node.description:
                    lines.append(f"  {node.description}")

                if isinstance(node, DataSourceNode):
                    lines.append(f"  Table: {node.table}")
                    if node.primaryKey:
                        lines.append(f"  Primary key: {node.primaryKey}")
                    for col_name, col in node.columns.items():
                        term = f" ({col.businessTerm})" if col.businessTerm else ""
                        lines.append(f"  - `{col_name}` [{col.dataType}]: {col.description}{term}")

                elif isinstance(node, AttributeNode):
                    if node.valueType != "STR":
                        lines.append(f"  Value type: {node.valueType}")
                    if node.isMultiple:
                        lines.append("  Multiple values: yes")
                    if node.isScored:
                        lines.append("  Scored: yes")
                    if node.options:
                        opts = ", ".join(f"{o.name}={o.value}" for o in node.options)
                        lines.append(f"  Options: {opts}")
                    for rule in rules_by_attr.get(key, []):
                        srcs = ""
                        if rule.sources:
                            srcs = f" from {', '.join(f'{s.datasource}.{s.column}' for s in rule.sources)}"
                        lines.append(f"  Rule: {rule.type}{srcs}")

                elif isinstance(node, SegmentNode):
                    for c in node.conditions:
                        score_str = f" (minScore={c.minScore})" if c.minScore else ""
                        lines.append(f"  - {c.attribute} {c.operator} {c.value}{score_str}")
                    for st in strategies_by_segment.get(key, []):
                        detail = st.strategy or st.template or ""
                        lines.append(f"  Strategy[{st.key}]: {detail}".rstrip())

                lines.append("")

        return "\n".join(lines)


def get_config_manager(config_dir: Optional[str] = None) -> ConfigManager:
    """Get the ConfigManager singleton instance."""
    return ConfigManager.get_instance(config_dir)
