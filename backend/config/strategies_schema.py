"""Pydantic models for the strategy config — the *action* layer.

The third concern alongside ontology (structure) and rules (attribute computation):
strategies define what action/tune fires for a segment (NBA/NBO and beyond).
Merchants author these independently of compute rules. Each Strategy references a
SegmentNode BY KEY; a referential-integrity validator enforces that the key resolves.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class Strategy(BaseModel):
    """A configurable action/scoring strategy attached to a segment.

    Generalizes the old hardcoded `SegmentActionsConfig{nba, nbo}`: NBA/NBO are now
    just instances with `key="nba"`/`key="nbo"`. Any number of custom strategies
    (e.g. "next_channel") can be configured without a schema change.
    """
    key: str  # arbitrary: "nba", "nbo", "next_channel", ...
    name: str = ""
    segment: str  # FK -> SegmentNode key in the ontology
    strategy: Optional[str] = None  # methodology id (was negotiation_style)
    template: Optional[str] = None
    params: Dict[str, Any] = {}  # free-form tuning: tone, incentive_format, ...


class StrategiesConfig(BaseModel):
    """Strategy config — the only home for strategies at runtime."""
    version: str = "1.0.0"
    site_id: str = "default"
    strategies: List[Strategy] = []
