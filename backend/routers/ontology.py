"""FastAPI router for unified ontology (v3) endpoints."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from pydantic import ValidationError

from backend.auth import get_current_user, require_admin, UserContext
from backend.config import get_config_manager
from backend.config.scoring import ScoringError
from backend.config.schemas import (
    UnifiedOntologyConfig, AttributeNode, SegmentNode, TaxonomyOptionConfig, ScoringConfig,
)
from backend.config.rules_schema import RulesConfig
from backend.config.strategies_schema import StrategiesConfig
from backend.config.integrity import IntegrityError
from backend.config.action_log import log_action

router = APIRouter(prefix="/api/ontology", tags=["ontology"], dependencies=[Depends(get_current_user)])


class NodeOptionRequest(BaseModel):
    name: str
    value: str
    semanticDefinition: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class NodeOptionDeleteRequest(BaseModel):
    value: str


class ScoreRequest(BaseModel):
    responses: Dict[str, str]


class SegmentMatchRequest(BaseModel):
    attributes: Dict[str, Any]


class ResolveStrategyRequest(BaseModel):
    segment_key: str
    strategy_key: str
    context: Dict[str, Any] = {}


class LabelScoresRequest(BaseModel):
    contributions: List[Dict[str, Any]] = []  # [{"source": str, "points": {value: number}}]
    scoring: Optional[ScoringConfig] = None  # override thresholds (e.g. behavioral "score=2 ⇒ primary")


@router.get("")
async def get_ontology():
    """Get the full ontology config."""
    cm = get_config_manager()
    try:
        config = cm.load_ontology()
        return config.model_dump()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Ontology config not found")


@router.put("")
async def replace_ontology(
    config: UnifiedOntologyConfig, user: UserContext = Depends(require_admin)
):
    """Replace the full ontology config."""
    cm = get_config_manager()
    cm.save_ontology(config)
    return {"status": "success", "version": config.version, "node_count": len(config.nodes)}


@router.get("/nodes")
async def list_nodes(type: Optional[str] = None):
    """List ontology nodes, optionally filtered by type."""
    cm = get_config_manager()
    try:
        nodes = cm.get_nodes(node_type=type)
        return {k: v.model_dump() for k, v in nodes.items()}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Ontology config not found")


@router.get("/nodes/{key}")
async def get_node(key: str):
    """Get a single ontology node by key."""
    cm = get_config_manager()
    node = cm.get_node(key)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node '{key}' not found")
    return node.model_dump()


@router.post("/nodes/{key}", status_code=201)
async def create_node(
    key: str, body: Dict[str, Any], user: UserContext = Depends(require_admin)
):
    """Create a new ontology node (datasource, attribute, or segment)."""
    cm = get_config_manager()
    try:
        temp = UnifiedOntologyConfig(nodes={key: body})
        node = temp.nodes[key]
        cm.add_node(key, node)
        return {"status": "success", "key": key, "type": node.type}
    except (ValueError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/nodes/{key}")
async def update_node(
    key: str, body: Dict[str, Any], user: UserContext = Depends(require_admin)
):
    """Update an existing ontology node."""
    cm = get_config_manager()
    if cm.get_node(key) is None:
        raise HTTPException(status_code=404, detail=f"Node '{key}' not found")
    try:
        temp = UnifiedOntologyConfig(nodes={key: body})
        node = temp.nodes[key]
        cm.update_node(key, node)
        return {"status": "success", "key": key}
    except (ValueError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/nodes/{key}")
async def delete_node(key: str, user: UserContext = Depends(require_admin)):
    """Delete an ontology node (cascade protection)."""
    cm = get_config_manager()
    if cm.get_node(key) is None:
        raise HTTPException(status_code=404, detail=f"Node '{key}' not found")
    try:
        cm.delete_node(key)
        return {"status": "success", "key": key}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/nodes/{key}/options")
async def add_node_option(
    key: str, request: NodeOptionRequest, user: UserContext = Depends(require_admin)
):
    """Add an option to an attribute node."""
    cm = get_config_manager()
    try:
        option = TaxonomyOptionConfig(
            name=request.name, value=request.value,
            semanticDefinition=request.semanticDefinition,
            metadata=request.metadata,
        )
        cm.add_node_option(key, option)
        return {"status": "success", "key": key, "option": request.value}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/nodes/{key}/options")
async def delete_node_option(
    key: str, request: NodeOptionDeleteRequest, user: UserContext = Depends(require_admin)
):
    """Remove an option from an attribute node."""
    cm = get_config_manager()
    try:
        cm.delete_node_option(key, request.value)
        return {"status": "success", "key": key, "removed": request.value}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/nodes/{key}/score")
async def score_endpoint(key: str, request: ScoreRequest, user: UserContext = Depends(get_current_user)):
    """Score responses against an attribute's quiz rule."""
    cm = get_config_manager()
    node = cm.get_node(key)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node '{key}' not found")
    if not isinstance(node, AttributeNode):
        raise HTTPException(status_code=400, detail=f"Node '{key}' is not an attribute")

    try:
        result = cm.get_evaluator().score_quiz(key, request.responses)
    except ScoringError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        from backend.db import get_engine
        engine = get_engine()
        if engine:
            log_action(engine, user.site_id, "score", key,
                       request_data={"responses": request.responses},
                       response_data=result, executed_by=user.user_id)
    except Exception:
        pass

    return {"attribute_key": key, **result}


@router.post("/nodes/{key}/label")
async def label_scores_endpoint(key: str, request: LabelScoresRequest):
    """Aggregate caller-supplied scoring contributions and label primary/secondary.

    Stateless — the caller owns the running tally and passes all contributions each call.
    """
    from backend.config.scoring import ScoreContribution
    cm = get_config_manager()
    node = cm.get_node(key)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node '{key}' not found")
    if not isinstance(node, AttributeNode):
        raise HTTPException(status_code=400, detail=f"Node '{key}' is not an attribute")
    contribs = [ScoreContribution(**c) for c in request.contributions]
    try:
        result = cm.get_evaluator().label_scores(key, contribs, scoring=request.scoring)
    except ScoringError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"attribute_key": key, **result}


@router.post("/resolve-segments")
async def resolve_segments(request: SegmentMatchRequest):
    """Resolve which segments match given user attributes."""
    cm = get_config_manager()
    try:
        config = cm.load_ontology()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Ontology config not found")

    segments = {k: v for k, v in config.nodes.items() if isinstance(v, SegmentNode)}
    evaluator = cm.get_evaluator()
    matched = []

    for seg_key, seg in segments.items():
        is_match, reasoning = evaluator.evaluate_segment(seg_key, request.attributes)
        if is_match:
            matched.append({
                "key": seg_key,
                "name": seg.name,
                "description": seg.description,
                "reasoning": reasoning,
                "strategies": [s.key for s in evaluator.strategies_for(seg_key)],
            })

    return {
        "site_id": config.site_id,
        "ontology_version": config.version,
        "matched": matched,
        "total_segments_evaluated": len(segments),
    }


@router.post("/resolve-strategy")
async def resolve_strategy(request: ResolveStrategyRequest):
    """Resolve a configured strategy (NBA/NBO/custom) for a segment."""
    cm = get_config_manager()
    node = cm.get_node(request.segment_key)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Segment '{request.segment_key}' not found")
    if not isinstance(node, SegmentNode):
        raise HTTPException(status_code=400, detail=f"Node '{request.segment_key}' is not a segment")

    evaluator = cm.get_evaluator()
    try:
        resolved = evaluator.resolve_strategy(request.segment_key, request.strategy_key, request.context)
    except ScoringError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "segment_name": node.name,
        **resolved,
        "taxonomy_context": evaluator.build_taxonomy_context(request.segment_key),
        "execution_hints": {
            "sources_used": [c.attribute for c in node.conditions],
        },
    }


# ── Rule/score engine config (behavior layer) ──────────────────────────────

@router.get("/rules")
async def get_rules():
    """Get the compute-rule config."""
    cm = get_config_manager()
    return cm.load_rules().model_dump()


@router.put("/rules")
async def replace_rules(config: RulesConfig, user: UserContext = Depends(require_admin)):
    """Replace the compute-rule config (validated against the ontology)."""
    cm = get_config_manager()
    try:
        cm.save_rules(config)
    except IntegrityError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "status": "success",
        "version": config.version,
        "compute_rules": len(config.computeRules),
    }


# ── Strategy config (action layer) ─────────────────────────────────────────

@router.get("/strategies")
async def get_strategies():
    """Get the strategy config (action tunes per segment)."""
    cm = get_config_manager()
    return cm.load_strategies().model_dump()


@router.put("/strategies")
async def replace_strategies(
    config: StrategiesConfig, user: UserContext = Depends(require_admin)
):
    """Replace the strategy config (validated against the ontology)."""
    cm = get_config_manager()
    try:
        cm.save_strategies(config)
    except IntegrityError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "status": "success",
        "version": config.version,
        "strategies": len(config.strategies),
    }
