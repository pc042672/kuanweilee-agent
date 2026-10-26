"""External action connector layer — the bridge to the customer's CDP system.

The agent's marketing plan states WHAT to execute and WHY; the downstream CDP
system (via its own APIs/agents/MCP, provided later) owns HOW delivery
happens. This module defines:

- MarketingPlan / ExternalAction — the typed handoff payload
- ExternalActionAdapter — narrow ABC every connector implements
- DryRunAdapter — default stub: logs + records to action_executions
- a per-site, name-keyed registry so real adapters drop in without touching
  callers (an ADK MCPToolset mount or a REST adapter both fit behind it)
- read-side connector stubs (taxonomy / campaign list / entity lookup)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel

logger = logging.getLogger("ai_cdp.external_actions")

ActionType = Literal[
    "setup_campaign",
    "schedule_campaign",
    "setup_segmentation",
    "setup_score_rule",
    "setup_behavior_rule",
]

Channel = Literal["edm", "sms", "web_popup"]


class Kpi(BaseModel):
    metric: str
    target: Optional[str] = None
    timeframe: Optional[str] = None


class SegmentationBasis(BaseModel):
    """What the audience is based on: a taxonomy segment or behavioral criteria."""
    basis: Literal["taxonomy", "behavioral"]
    segment_key: Optional[str] = None       # taxonomy: ontology SegmentNode key
    conditions: Optional[List[Dict[str, Any]]] = None  # resolved conditions snapshot
    behavior_criteria: Optional[str] = None  # behavioral: criteria description / SQL


class Audience(BaseModel):
    size: Optional[int] = None
    source_query: Optional[str] = None       # the SQL the audience came from
    snapshot_ref: Optional[str] = None       # export/table reference if materialized


class StrategyRef(BaseModel):
    key: Optional[str] = None                # strategies config key (nba/nbo/...)
    message: Optional[str] = None            # rendered message/template
    params: Dict[str, Any] = {}


class MarketingPlan(BaseModel):
    """WHAT to execute and WHY — evidence-backed, channel decided with rationale."""
    goal: str
    kpi: Optional[Kpi] = None
    segmentation: SegmentationBasis
    audience: Audience = Audience()
    analysis_evidence: List[str] = []         # key findings supporting the plan
    strategy: StrategyRef = StrategyRef()
    channel: Optional[Channel] = None
    channel_rationale: Optional[str] = None
    channel_params: Dict[str, Any] = {}


class ExternalAction(BaseModel):
    action_type: ActionType
    plan: MarketingPlan
    schedule: Optional[str] = None            # schedule_campaign: cron/ISO datetime


class ExecutionRecord(BaseModel):
    status: Literal["dry_run", "submitted", "failed"]
    adapter: str
    detail: str = ""
    external_ref: Optional[str] = None        # downstream system's id, when real


class ExternalActionAdapter(ABC):
    """One narrow seam. Real CDP connectors (REST or MCP-backed) implement this."""

    name: str = "base"

    @abstractmethod
    async def execute(self, action: ExternalAction) -> ExecutionRecord: ...


class DryRunAdapter(ExternalActionAdapter):
    """Default stub: validates + logs the plan; nothing leaves the system."""

    name = "dry_run"

    async def execute(self, action: ExternalAction) -> ExecutionRecord:
        logger.info(
            "DRY-RUN %s | goal=%r segment=%s channel=%s",
            action.action_type, action.plan.goal,
            action.plan.segmentation.segment_key or action.plan.segmentation.basis,
            action.plan.channel,
        )
        return ExecutionRecord(
            status="dry_run",
            adapter=self.name,
            detail=f"{action.action_type} validated; no external system configured yet",
        )


# ── registry ──────────────────────────────────────────────────────

_DEFAULT = DryRunAdapter()
_registry: Dict[str, ExternalActionAdapter] = {}


def register_adapter(adapter: ExternalActionAdapter, site_id: Optional[int] = None) -> None:
    """Register a connector globally or for one site (key 'site:{id}:{name}')."""
    key = f"site:{site_id}:{adapter.name}" if site_id is not None else adapter.name
    _registry[key] = adapter


def get_adapter(site_id: Optional[int] = None, name: Optional[str] = None) -> ExternalActionAdapter:
    """Resolve the connector for a site; falls back to the dry-run stub."""
    if name and site_id is not None and f"site:{site_id}:{name}" in _registry:
        return _registry[f"site:{site_id}:{name}"]
    if name and name in _registry:
        return _registry[name]
    return _DEFAULT


async def execute_action(
    action: ExternalAction,
    *,
    site_id: int,
    executed_by: Optional[int] = None,
    adapter_name: Optional[str] = None,
) -> ExecutionRecord:
    """Dispatch an action through the site's adapter and audit it."""
    adapter = get_adapter(site_id, adapter_name)
    try:
        record = await adapter.execute(action)
    except Exception as e:
        logger.exception("external action failed")
        record = ExecutionRecord(status="failed", adapter=adapter.name, detail=str(e))

    from services.guardrails import record_action
    record_action(
        site_id=site_id,
        action_type=action.action_type,
        target=action.plan.segmentation.segment_key,
        request_data=action.model_dump(mode="json"),
        response_data=record.model_dump(mode="json"),
        status="failed" if record.status == "failed" else "succeeded",
        error_message=record.detail if record.status == "failed" else None,
        executed_by=executed_by,
    )
    return record


# ── read-side connector stubs (real MCP/APIs drop in later) ──────

def get_taxonomy_stub(site_id: int) -> Dict[str, Any]:
    """Until the external CDP API arrives, taxonomy = our ontology segments."""
    from revive_agent.tools._infra import get_config
    segments = get_config().get_nodes(node_type="segment")
    return {
        "source": "internal_ontology",
        "segments": {
            k: {"name": n.name, "description": n.description}
            for k, n in segments.items()
        },
    }


def list_campaigns_stub(site_id: int) -> Dict[str, Any]:
    """Past executions stand in for the external campaign list."""
    from db import get_engine
    from sqlalchemy import text
    engine = get_engine()
    if engine is None:
        return {"source": "stub", "campaigns": []}
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, action_type, target_node_key, execution_status, completed_at "
            "FROM action_executions WHERE site_id = :sid "
            "AND action_type LIKE '%campaign%' ORDER BY id DESC LIMIT 20"
        ), {"sid": site_id}).fetchall()
    return {
        "source": "action_executions",
        "campaigns": [
            {"id": r[0], "type": r[1], "segment": r[2], "status": r[3],
             "completed_at": str(r[4])}
            for r in rows
        ],
    }
