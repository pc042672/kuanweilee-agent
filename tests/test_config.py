"""Tests for backend/config/loader.py — ConfigManager with v3 ontology."""

import json
import pytest

from config.loader import ConfigManager
from config.schemas import (
    UnifiedOntologyConfig, AttributeNode, SegmentNode, DataSourceNode,
    SegmentCondition, TaxonomyOptionConfig,
)


@pytest.fixture
def config_dir(tmp_path):
    """Create a temp config directory with a minimal v3 ontology."""
    ontology = {
        "version": "3.0.0",
        "site_id": "default",
        "nodes": {
            "gender": {
                "type": "attribute",
                "name": "Gender",
                "description": "Member gender",
                "valueType": "STR",
                "options": [
                    {"name": "Male", "value": "01"},
                    {"name": "Female", "value": "02"},
                ],
            },
            "high_value_female": {
                "type": "segment",
                "name": "High Value Female",
                "description": "Female high spenders",
                "conditions": [
                    {"attribute": "gender", "operator": "EQUAL", "value": "02"},
                ],
            },
        },
    }
    (tmp_path / "ontology.json").write_text(json.dumps(ontology))
    return tmp_path


class TestConfigManagerLoad:
    def test_load_ontology_returns_v3(self, config_dir):
        mgr = ConfigManager(config_dir=str(config_dir))
        config = mgr.load_ontology()
        assert isinstance(config, UnifiedOntologyConfig)
        assert config.version == "3.0.0"
        assert len(config.nodes) == 2

    def test_caching(self, config_dir):
        mgr = ConfigManager(config_dir=str(config_dir))
        c1 = mgr.load_ontology()
        c2 = mgr.load_ontology()
        assert c1 is c2

    def test_get_nodes_all(self, config_dir):
        mgr = ConfigManager(config_dir=str(config_dir))
        nodes = mgr.get_nodes()
        assert len(nodes) == 2

    def test_get_nodes_filtered(self, config_dir):
        mgr = ConfigManager(config_dir=str(config_dir))
        segments = mgr.get_nodes(node_type="segment")
        assert len(segments) == 1
        assert "high_value_female" in segments

    def test_get_node(self, config_dir):
        mgr = ConfigManager(config_dir=str(config_dir))
        node = mgr.get_node("gender")
        assert isinstance(node, AttributeNode)
        assert node.name == "Gender"

    def test_get_node_missing(self, config_dir):
        mgr = ConfigManager(config_dir=str(config_dir))
        assert mgr.get_node("nonexistent") is None


class TestConfigManagerReload:
    def test_reload_swaps(self, config_dir):
        mgr = ConfigManager(config_dir=str(config_dir))
        old = mgr.load_ontology()
        assert old.version == "3.0.0"

        new_data = {"version": "4.0.0", "site_id": "default", "nodes": {}}
        (config_dir / "ontology.json").write_text(json.dumps(new_data))

        mgr.reload()
        new = mgr.load_ontology()
        assert new.version == "4.0.0"

    def test_reload_handles_missing_file(self, config_dir):
        mgr = ConfigManager(config_dir=str(config_dir))
        mgr.load_ontology()
        (config_dir / "ontology.json").unlink()
        mgr.reload()
        assert mgr._ontology is None


class TestConfigManagerNodeCRUD:
    def test_add_node(self, config_dir):
        mgr = ConfigManager(config_dir=str(config_dir))
        node = AttributeNode(name="Age", valueType="NUM")
        mgr.add_node("age", node)
        assert mgr.get_node("age") is not None

    def test_add_duplicate_raises(self, config_dir):
        mgr = ConfigManager(config_dir=str(config_dir))
        node = AttributeNode(name="Dup")
        with pytest.raises(ValueError, match="already exists"):
            mgr.add_node("gender", node)

    def test_update_node(self, config_dir):
        mgr = ConfigManager(config_dir=str(config_dir))
        node = AttributeNode(name="Gender Updated", valueType="STR")
        mgr.update_node("gender", node)
        assert mgr.get_node("gender").name == "Gender Updated"

    def test_update_missing_raises(self, config_dir):
        mgr = ConfigManager(config_dir=str(config_dir))
        with pytest.raises(ValueError, match="not found"):
            mgr.update_node("missing", AttributeNode(name="X"))

    def test_delete_node(self, config_dir):
        mgr = ConfigManager(config_dir=str(config_dir))
        # Add a standalone node, then delete it
        mgr.add_node("temp", AttributeNode(name="Temp"))
        mgr.delete_node("temp")
        assert mgr.get_node("temp") is None

    def test_delete_referenced_raises(self, config_dir):
        mgr = ConfigManager(config_dir=str(config_dir))
        with pytest.raises(ValueError, match="referenced by"):
            mgr.delete_node("gender")  # referenced by high_value_female segment

    def test_add_segment_with_bad_ref_raises(self, config_dir):
        mgr = ConfigManager(config_dir=str(config_dir))
        seg = SegmentNode(
            name="Bad",
            conditions=[SegmentCondition(attribute="nonexistent", operator="EQUAL", value="x")],
        )
        with pytest.raises(ValueError, match="unknown attribute"):
            mgr.add_node("bad_seg", seg)


class TestConfigManagerOptions:
    def test_add_option(self, config_dir):
        mgr = ConfigManager(config_dir=str(config_dir))
        opt = TaxonomyOptionConfig(name="Other", value="03")
        mgr.add_node_option("gender", opt)
        node = mgr.get_node("gender")
        assert any(o.value == "03" for o in node.options)

    def test_add_option_to_non_attribute_raises(self, config_dir):
        mgr = ConfigManager(config_dir=str(config_dir))
        opt = TaxonomyOptionConfig(name="X", value="x")
        with pytest.raises(ValueError, match="not an attribute"):
            mgr.add_node_option("high_value_female", opt)

    def test_delete_option(self, config_dir):
        mgr = ConfigManager(config_dir=str(config_dir))
        mgr.delete_node_option("gender", "01")
        node = mgr.get_node("gender")
        assert not any(o.value == "01" for o in node.options)

    def test_delete_option_missing_raises(self, config_dir):
        mgr = ConfigManager(config_dir=str(config_dir))
        with pytest.raises(ValueError, match="not found"):
            mgr.delete_node_option("gender", "99")


class TestConfigManagerPrompt:
    def test_format_ontology_for_prompt(self, config_dir):
        mgr = ConfigManager(config_dir=str(config_dir))
        prompt = mgr.format_ontology_for_prompt()
        assert "## CDP Ontology" in prompt
        assert "Gender" in prompt
        assert "High Value Female" in prompt
