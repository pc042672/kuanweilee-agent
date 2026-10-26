"""Pydantic models for the compute-rule config — the *attribute computation* layer.

Separation of concerns (OWL-vs-SWRL style): the ontology (schemas.py) declares
*what exists*; this module declares *how an attribute is computed* (sql/quiz). The
*action* layer (what fires for a segment) lives separately in strategies_schema.py.

Every rule references ontology entities BY KEY only; a referential-integrity
validator (integrity.py) enforces that those keys resolve.
"""

from typing import List, Literal, Optional
from pydantic import BaseModel

from .schemas import SourceRef, QuizSectionConfig, ValueMappingConfig


ComputeRuleType = Literal["sql", "quiz", "labeling_rule"]


class ComputeRule(BaseModel):
    """How an attribute's value is computed. References an ontology AttributeNode by key.

    Relocated from the old `AttributeNode.rules: List[RuleDef]` — the attribute now
    holds only its identity and value domain (structure); the computation lives here.
    Per the PRD this is a semantic sidecar: `sql` rules carry the expression + sources
    as a HINT for the DE-Agent to execute; `quiz` rules are scored in-process.
    """
    attribute: str  # FK -> AttributeNode key in the ontology
    type: ComputeRuleType
    sources: List[SourceRef] = []  # FK -> DataSourceNode keys (datasource + column)
    sql: Optional[str] = None
    quiz: Optional[QuizSectionConfig] = None
    valueMappings: List[ValueMappingConfig] = []


class RulesConfig(BaseModel):
    """Compute-rule config — the home for attribute compute rules at runtime."""
    version: str = "1.0.0"
    site_id: str = "default"
    computeRules: List[ComputeRule] = []
