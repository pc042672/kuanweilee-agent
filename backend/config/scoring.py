"""Rule/score engine — the *behavior* layer that operates on the ontology.

The ontology (schemas.py) declares structure; this module computes with it. Per the
PRD this is a *stateless* semantic sidecar: it aggregates/labels scoring signals,
scores quizzes, matches segments, resolves strategies, and builds LLM context — it
does NOT execute SQL, orchestrate pipelines, or hold per-subject state (callers own
any running tally). `OntologyEvaluator` is the front door.

Generic scoring model: a `ScoreContribution` is points a signal contributes to one
or more category values (`{value: delta}`). Signals are source-agnostic — an
assessment, a selection, an acceptance, a behavioral cue all look the same to the
engine. The caller accumulates contributions (it owns the tally) and asks the engine
to `aggregate` + `label` them into primary/secondary by threshold.
"""

from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

from .schemas import (
    UnifiedOntologyConfig, AttributeNode, SegmentNode, SegmentCondition, ScoringConfig,
)
from .rules_schema import RulesConfig, ComputeRule
from .strategies_schema import StrategiesConfig, Strategy


class ScoringError(ValueError):
    """Raised when scoring input is invalid (bad question/option ID, missing data)."""


class ScoreContribution(BaseModel):
    """Points a single signal contributes toward category values.

    `source` is a free-form tag for traceability (e.g. "assessment", "selection",
    "acceptance"); the engine does not interpret it. `points` maps category value -> delta.
    """
    source: str = ""
    points: Dict[str, float] = {}


def aggregate(contributions: List[ScoreContribution]) -> Dict[str, float]:
    """Sum points per category value across all contributions (pure, stateless)."""
    totals: Dict[str, float] = {}
    for c in contributions:
        for value, pts in c.points.items():
            totals[value] = totals.get(value, 0) + pts
    return totals


def label(scores: Dict[str, float], scoring: ScoringConfig,
          name_lookup: Optional[Dict[str, str]] = None) -> Dict:
    """Threshold a category->score map into primary/secondary + all_scores (pure)."""
    name_lookup = name_lookup or {}
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary: List[Dict] = []
    secondary: List[Dict] = []
    for value_key, value_score in sorted_scores:
        entry = {"value": value_key, "score": value_score, "name": name_lookup.get(value_key, value_key)}
        if value_score >= scoring.primaryThreshold and len(primary) < scoring.maxPrimary:
            primary.append(entry)
        elif value_score >= scoring.secondaryThreshold and len(secondary) < scoring.maxSecondary:
            secondary.append(entry)
    return {"primary": primary, "secondary": secondary, "all_scores": dict(sorted_scores)}


def _name_lookup(attribute: AttributeNode, rule: Optional[ComputeRule]) -> Dict[str, str]:
    """Build value_key -> display name. Attribute options override rule valueMappings."""
    lookup: Dict[str, str] = {}
    if rule:
        for vm in rule.valueMappings:
            lookup[vm.value] = vm.name
    for opt in attribute.options:
        lookup[opt.value] = opt.name
    return lookup


def _quiz_points(quiz_rule: ComputeRule, responses: Dict[str, str]) -> Dict[str, float]:
    """Sum the category points a set of quiz responses contributes (one signal's worth)."""
    points: Dict[str, float] = {}
    for qid, oid in responses.items():
        question = next((q for q in quiz_rule.quiz.questions if q.id == qid), None)
        if not question:
            raise ScoringError(f"Unknown question '{qid}'")
        option = next((o for o in question.options if o.id == oid), None)
        if not option:
            raise ScoringError(f"Unknown option '{oid}' for question '{qid}'")
        for value_key, pts in option.mappings.items():
            points[value_key] = points.get(value_key, 0) + pts
    return points


def score(attribute: AttributeNode, rules: List[ComputeRule], responses: Dict[str, str]) -> Dict:
    """One-shot assessment scoring: sum a quiz rule's responses and label by threshold.

    Equivalent to aggregate([assessment contribution]) + label — kept as a convenience
    for the single-signal case.
    """
    quiz_rule = next((r for r in rules if r.quiz and r.quiz.questions), None)
    if not quiz_rule:
        raise ScoringError(f"Attribute '{attribute.name}' has no quiz rule")
    if not responses:
        raise ScoringError("No responses provided")
    points = _quiz_points(quiz_rule, responses)
    return label(points, quiz_rule.quiz.scoring, _name_lookup(attribute, quiz_rule))


def _semantic_definition(value: Any, attribute: AttributeNode, rules: List[ComputeRule]) -> Optional[str]:
    """Semantic definition for a value: attribute option (preferred) then rule valueMapping."""
    for opt in attribute.options:
        if opt.semanticDefinition and str(opt.value) == str(value):
            return opt.semanticDefinition
    for rule in rules:
        for vm in rule.valueMappings:
            if vm.semanticDefinition and str(vm.value) == str(value):
                return vm.semanticDefinition
    return None


def build_taxonomy_context(
    segment: SegmentNode,
    config: UnifiedOntologyConfig,
    rules: RulesConfig,
) -> List[str]:
    """Resolve semantic definitions for a segment's referenced attributes.

    Prefers the attribute option's semanticDefinition (structure), falling back to a
    compute rule's valueMapping (behavior).
    """
    rules_by_attr: Dict[str, List[ComputeRule]] = {}
    for r in rules.computeRules:
        rules_by_attr.setdefault(r.attribute, []).append(r)

    context: List[str] = []
    for cond in segment.conditions:
        attr_node = config.nodes.get(cond.attribute)
        if not isinstance(attr_node, AttributeNode):
            continue
        sd = _semantic_definition(cond.value, attr_node, rules_by_attr.get(cond.attribute, []))
        if sd:
            context.append(f"{attr_node.name}: {sd}")
    return context


def _apply_operator(cond: SegmentCondition, attr_value: Any) -> bool:
    """Evaluate a single condition operator against a value."""
    if cond.operator == "EQUAL":
        return str(attr_value) == str(cond.value)
    if cond.operator == "NOT_EQUAL":
        return str(attr_value) != str(cond.value)
    if cond.operator == ">=":
        try:
            return float(attr_value) >= float(cond.value)
        except (ValueError, TypeError):
            return False
    if cond.operator == "<=":
        try:
            return float(attr_value) <= float(cond.value)
        except (ValueError, TypeError):
            return False
    if cond.operator == "BETWEEN":
        try:
            v = float(attr_value)
            return float(cond.value) <= v <= float(cond.secondValue)
        except (ValueError, TypeError):
            return False
    if cond.operator == "IN":
        if isinstance(cond.value, list):
            return str(attr_value) in {str(v) for v in cond.value}
        return False
    return False


def evaluate_segment(seg: SegmentNode, attributes: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Evaluate whether a set of attributes matches a segment.

    Returns:
        (is_match, reasoning_trace) — pure function, no I/O.
    """
    reasoning: List[str] = []
    all_met = True

    for cond in seg.conditions:
        attr = attributes.get(cond.attribute)
        if attr is None:
            reasoning.append(f"MISS: attribute '{cond.attribute}' not provided")
            all_met = False
            continue

        attr_value = attr.get("value") if isinstance(attr, dict) else attr
        attr_score = attr.get("score") if isinstance(attr, dict) else None

        met = _apply_operator(cond, attr_value)

        if met and cond.minScore is not None:
            if attr_score is None or float(attr_score) < cond.minScore:
                reasoning.append(f"MISS: '{cond.attribute}' score {attr_score} < minScore {cond.minScore}")
                met = False

        if met:
            reasoning.append(f"MATCH: '{cond.attribute}' {cond.operator} {cond.value}")
        else:
            if not any(cond.attribute in r for r in reasoning if r.startswith("MISS")):
                reasoning.append(f"MISS: '{cond.attribute}' {cond.operator} {cond.value} (got {attr_value})")
            all_met = False

    is_match = all_met if seg.logic == "ALL" else any("MATCH" in r for r in reasoning)
    return is_match, reasoning


# ═══════════════════════════════════════════════════════════════
# OntologyEvaluator — the engine front door (structure + behavior)
# ═══════════════════════════════════════════════════════════════

class OntologyEvaluator:
    """Scores quizzes, matches segments, and resolves strategies against a site's
    ontology (structure) + rules (compute) + strategies (action). Indexes by ontology
    FK for O(1) lookup."""

    def __init__(self, ontology: UnifiedOntologyConfig, rules: RulesConfig,
                 strategies: StrategiesConfig):
        self.ontology = ontology
        self.rules = rules
        self.strategies = strategies
        self._by_attr: Dict[str, List[ComputeRule]] = {}
        for r in rules.computeRules:
            self._by_attr.setdefault(r.attribute, []).append(r)
        self._by_segment: Dict[str, List[Strategy]] = {}
        for s in strategies.strategies:
            self._by_segment.setdefault(s.segment, []).append(s)

    def compute_rules_for(self, attribute_key: str) -> List[ComputeRule]:
        return self._by_attr.get(attribute_key, [])

    def strategies_for(self, segment_key: str) -> List[Strategy]:
        return self._by_segment.get(segment_key, [])

    def _attribute(self, attribute_key: str) -> AttributeNode:
        node = self.ontology.nodes.get(attribute_key)
        if not isinstance(node, AttributeNode):
            raise ScoringError(f"'{attribute_key}' is not an attribute node")
        return node

    def _quiz_rule(self, attribute_key: str) -> ComputeRule:
        rule = next((r for r in self.compute_rules_for(attribute_key) if r.quiz and r.quiz.questions), None)
        if rule is None:
            raise ScoringError(f"Attribute '{attribute_key}' has no quiz rule")
        return rule

    def score_quiz(self, attribute_key: str, responses: Dict[str, str]) -> Dict:
        """One-shot: score quiz responses for an attribute (single assessment signal)."""
        return score(self._attribute(attribute_key), self.compute_rules_for(attribute_key), responses)

    def quiz_contribution(self, attribute_key: str, responses: Dict[str, str],
                          source: str = "assessment") -> ScoreContribution:
        """Turn quiz responses into a ScoreContribution the caller can accumulate with
        other signals (selection, acceptance, ...) toward a running tally it owns."""
        if not responses:
            raise ScoringError("No responses provided")
        return ScoreContribution(source=source, points=_quiz_points(self._quiz_rule(attribute_key), responses))

    def label_scores(self, attribute_key: str, contributions: List[ScoreContribution],
                     scoring: Optional[ScoringConfig] = None) -> Dict:
        """Aggregate caller-supplied contributions for a category attribute and label
        primary/secondary. Stateless: the caller passes the full set of contributions
        (its tally) each call. `scoring` defaults to the attribute's quiz thresholds."""
        attribute = self._attribute(attribute_key)
        if scoring is None:
            quiz_rule = next((r for r in self.compute_rules_for(attribute_key) if r.quiz), None)
            scoring = quiz_rule.quiz.scoring if quiz_rule and quiz_rule.quiz else ScoringConfig()
        return label(aggregate(contributions), scoring, _name_lookup(attribute, None))

    def evaluate_segment(self, segment_key: str, attributes: Dict[str, Any]) -> Tuple[bool, List[str]]:
        node = self.ontology.nodes.get(segment_key)
        if not isinstance(node, SegmentNode):
            raise ScoringError(f"'{segment_key}' is not a segment node")
        return evaluate_segment(node, attributes)

    def build_taxonomy_context(self, segment_key: str) -> List[str]:
        node = self.ontology.nodes.get(segment_key)
        if not isinstance(node, SegmentNode):
            raise ScoringError(f"'{segment_key}' is not a segment node")
        return build_taxonomy_context(node, self.ontology, self.rules)

    def resolve_strategy(
        self, segment_key: str, strategy_key: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict:
        """Resolve a configured strategy (NBA/NBO/custom) for a segment.

        Renders `template` with the strategy's params merged with `context`.
        """
        strat = next((s for s in self.strategies_for(segment_key) if s.key == strategy_key), None)
        if strat is None:
            raise ScoringError(f"Segment '{segment_key}' has no strategy '{strategy_key}'")
        fill = {**strat.params, **(context or {})}
        message = strat.template
        if message:
            try:
                message = message.format(**fill)
            except (KeyError, IndexError):
                pass  # leave unfilled placeholders rather than crash
        return {
            "key": strat.key,
            "name": strat.name,
            "segment": segment_key,
            "strategy": strat.strategy,
            "template": strat.template,
            "message": message,
            "params": strat.params,
        }
