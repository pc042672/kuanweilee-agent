"""Pydantic models for ontology configuration — the *structure* layer.

v3 unified ontology: DataSourceNode, AttributeNode, SegmentNode. These declare
*what exists* (tables, attributes + value domains, segments + membership conditions).
*How to use* the ontology — compute rules and strategies — lives in the rule/score
engine config (rules_schema.py), which references these nodes by key.

Shared scoring/quiz models below are imported by rules_schema.py.
"""

from typing import Annotated, Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Discriminator, Tag


# ═══════════════════════════════════════════════════════════════
# Shared Models
# ═══════════════════════════════════════════════════════════════

class TaxonomyOptionConfig(BaseModel):
    """Fixed/enumerated value for a taxonomy/attribute node."""
    name: str
    value: str
    semanticDefinition: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ValueMappingConfig(BaseModel):
    """Value mapping in a labeling rule or quiz."""
    name: str
    value: str
    semanticDefinition: Optional[str] = None


class QuizOptionConfig(BaseModel):
    """A single option within a quiz question."""
    id: str
    text: str
    mappings: Dict[str, int] = {}  # value_key -> score


class QuizQuestionConfig(BaseModel):
    """A quiz question with scored options."""
    id: str
    text: str
    options: List[QuizOptionConfig] = []


class ScoringConfig(BaseModel):
    """Scoring thresholds for result assignment (generic, not quiz-specific)."""
    primaryThreshold: int = 2
    secondaryThreshold: int = 1
    maxPrimary: int = 1
    maxSecondary: int = 2


class QuizSectionConfig(BaseModel):
    """Quiz questions and scoring configuration."""
    questions: List[QuizQuestionConfig] = []
    scoring: ScoringConfig = ScoringConfig()


SegmentOperator = Literal["EQUAL", "NOT_EQUAL", ">=", "<=", "BETWEEN", "IN"]


# ═══════════════════════════════════════════════════════════════
# v3 Unified Ontology (property graph)
# ═══════════════════════════════════════════════════════════════

NodeStatus = Literal["experimental", "active", "deprecated", "archived"]

class ColumnDef(BaseModel):
    """Column within a DataSource. The column name is the dict key in DataSourceNode.columns."""
    dataType: str = "STR"
    description: str = ""
    businessTerm: Optional[str] = None


class DataSourceNode(BaseModel):
    """Physical table/view in the customer's database."""
    type: Literal["datasource"] = "datasource"
    status: NodeStatus = "active"
    name: str
    table: str
    description: str = ""
    primaryKey: Optional[str] = None
    columns: Dict[str, ColumnDef] = {}


class SourceRef(BaseModel):
    """Structured reference from a Rule to a DataSource column."""
    datasource: str
    column: str


class AttributeNode(BaseModel):
    """Business concept — the 'what'. Structure only: identity + value domain.
    Computation lives in rules_schema.ComputeRule (keyed by this node's key)."""
    type: Literal["attribute"] = "attribute"
    status: NodeStatus = "active"
    name: str
    description: str = ""
    valueType: Literal["STR", "NUM", "DATE", "BOOL"] = "STR"
    isMultiple: bool = False
    isScored: bool = False
    options: List[TaxonomyOptionConfig] = []


class SegmentCondition(BaseModel):
    """One condition referencing an Attribute."""
    attribute: str
    operator: SegmentOperator
    value: Any
    secondValue: Optional[Any] = None
    minScore: Optional[float] = None


class SegmentNode(BaseModel):
    """Business audience — structure only: membership conditions.
    Actions/strategies live in rules_schema.Strategy (keyed by this node's key)."""
    type: Literal["segment"] = "segment"
    status: NodeStatus = "active"
    name: str
    description: str = ""
    conditions: List[SegmentCondition] = []
    logic: Literal["ALL", "ANY"] = "ALL"


def _get_node_type(v: Any) -> str:
    if isinstance(v, dict):
        return v.get("type", "")
    return getattr(v, "type", "")


OntologyNode = Annotated[
    Union[
        Annotated[DataSourceNode, Tag("datasource")],
        Annotated[AttributeNode, Tag("attribute")],
        Annotated[SegmentNode, Tag("segment")],
    ],
    Discriminator(_get_node_type),
]


class UnifiedOntologyConfig(BaseModel):
    """Single ontology config — the only config format at runtime."""
    version: str = "3.0.0"
    site_id: str = "default"
    nodes: Dict[str, OntologyNode] = {}


