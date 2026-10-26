"""Tests for backend/config/scoring.py — the rule/score engine (semantic sidecar).

Structure (AttributeNode/SegmentNode) lives in the ontology; behavior
(ComputeRule/Strategy) lives in RulesConfig. score() takes an attribute + its
compute rules; OntologyEvaluator is the front door (quiz scoring, segment match,
strategy resolution, taxonomy context).
"""

import pytest

from config.scoring import (
    score, build_taxonomy_context, ScoringError, OntologyEvaluator,
    aggregate, label, ScoreContribution,
)
from config.schemas import (
    AttributeNode, SegmentNode, SegmentCondition,
    UnifiedOntologyConfig, QuizSectionConfig,
    QuizQuestionConfig, QuizOptionConfig, ScoringConfig,
    TaxonomyOptionConfig, ValueMappingConfig,
)
from config.rules_schema import RulesConfig, ComputeRule
from config.strategies_schema import StrategiesConfig, Strategy


@pytest.fixture
def quiz_attribute():
    """(AttributeNode, [ComputeRule]) — an attribute with a quiz rule and options."""
    attr = AttributeNode(
        name="Archetype",
        isScored=True,
        options=[
            TaxonomyOptionConfig(name="Explorer", value="explorer", semanticDefinition="Driven by discovery"),
            TaxonomyOptionConfig(name="Hero", value="hero", semanticDefinition="Driven by achievement"),
            TaxonomyOptionConfig(name="Sage", value="sage", semanticDefinition="Driven by knowledge"),
        ],
    )
    rules = [
        ComputeRule(
            attribute="archetype",
            type="quiz",
            quiz=QuizSectionConfig(
                questions=[
                    QuizQuestionConfig(
                        id="q1", text="Choose:",
                        options=[
                            QuizOptionConfig(id="a", text="Explore", mappings={"explorer": 2, "hero": 1}),
                            QuizOptionConfig(id="b", text="Conquer", mappings={"hero": 2, "sage": 1}),
                            QuizOptionConfig(id="c", text="Study", mappings={"sage": 2, "explorer": 1}),
                        ],
                    ),
                    QuizQuestionConfig(
                        id="q2", text="Choose:",
                        options=[
                            QuizOptionConfig(id="a", text="Adventure", mappings={"explorer": 2}),
                            QuizOptionConfig(id="b", text="Challenge", mappings={"hero": 2}),
                        ],
                    ),
                ],
                scoring=ScoringConfig(primaryThreshold=3, secondaryThreshold=2, maxPrimary=1, maxSecondary=1),
            ),
        ),
    ]
    return attr, rules


class TestScore:
    def test_basic_scoring(self, quiz_attribute):
        attr, rules = quiz_attribute
        result = score(attr, rules, {"q1": "a", "q2": "a"})
        assert result["primary"][0]["value"] == "explorer"
        assert result["primary"][0]["score"] == 4
        assert result["primary"][0]["name"] == "Explorer"

    def test_secondary_result(self, quiz_attribute):
        attr, rules = quiz_attribute
        result = score(attr, rules, {"q1": "a", "q2": "b"})
        assert len(result["primary"]) == 1
        assert len(result["secondary"]) <= 1

    def test_all_scores_returned(self, quiz_attribute):
        attr, rules = quiz_attribute
        result = score(attr, rules, {"q1": "a", "q2": "a"})
        assert "explorer" in result["all_scores"]

    def test_no_quiz_rule_raises(self):
        attr = AttributeNode(name="No Quiz")
        with pytest.raises(ScoringError, match="no quiz rule"):
            score(attr, [], {"q1": "a"})

    def test_empty_responses_raises(self, quiz_attribute):
        attr, rules = quiz_attribute
        with pytest.raises(ScoringError, match="No responses"):
            score(attr, rules, {})

    def test_unknown_question_raises(self, quiz_attribute):
        attr, rules = quiz_attribute
        with pytest.raises(ScoringError, match="Unknown question"):
            score(attr, rules, {"q999": "a"})

    def test_unknown_option_raises(self, quiz_attribute):
        attr, rules = quiz_attribute
        with pytest.raises(ScoringError, match="Unknown option"):
            score(attr, rules, {"q1": "z"})

    def test_name_from_options(self, quiz_attribute):
        attr, rules = quiz_attribute
        result = score(attr, rules, {"q1": "a", "q2": "a"})
        for entry in result["primary"] + result["secondary"]:
            assert entry["name"] != entry["value"]


class TestBuildTaxonomyContext:
    def test_resolves_semantic_definition(self, quiz_attribute):
        attr, _ = quiz_attribute
        segment = SegmentNode(
            name="Explorer Campaign",
            conditions=[SegmentCondition(attribute="archetype", operator="EQUAL", value="explorer")],
        )
        config = UnifiedOntologyConfig(nodes={"archetype": attr, "explorer_campaign": segment})
        ctx = build_taxonomy_context(segment, config, RulesConfig())
        assert len(ctx) == 1
        assert "Driven by discovery" in ctx[0]

    def test_missing_attribute_skipped(self):
        segment = SegmentNode(
            name="Test",
            conditions=[SegmentCondition(attribute="missing", operator="EQUAL", value="x")],
        )
        config = UnifiedOntologyConfig(nodes={"test_seg": segment})
        assert build_taxonomy_context(segment, config, RulesConfig()) == []

    def test_no_matching_value_skipped(self, quiz_attribute):
        attr, _ = quiz_attribute
        segment = SegmentNode(
            name="Test",
            conditions=[SegmentCondition(attribute="archetype", operator="EQUAL", value="nonexistent")],
        )
        config = UnifiedOntologyConfig(nodes={"archetype": attr, "test_seg": segment})
        assert build_taxonomy_context(segment, config, RulesConfig()) == []

    def test_fallback_to_value_mappings(self):
        attr = AttributeNode(name="Test Attr", options=[])
        rules = RulesConfig(computeRules=[
            ComputeRule(
                attribute="test_attr", type="labeling_rule",
                valueMappings=[ValueMappingConfig(name="High", value="high", semanticDefinition="High value")],
            ),
        ])
        segment = SegmentNode(
            name="Test",
            conditions=[SegmentCondition(attribute="test_attr", operator="EQUAL", value="high")],
        )
        config = UnifiedOntologyConfig(nodes={"test_attr": attr, "test_seg": segment})
        ctx = build_taxonomy_context(segment, config, rules)
        assert len(ctx) == 1
        assert "High value" in ctx[0]


# ═══════════════════════════════════════════════════════════════
# OntologyEvaluator — quiz scoring, segment match, strategies
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def evaluator(quiz_attribute):
    attr, rules = quiz_attribute
    ontology = UnifiedOntologyConfig(nodes={
        "archetype": attr,
        "explorer_campaign": SegmentNode(
            name="Explorer Campaign",
            conditions=[SegmentCondition(attribute="archetype", operator="EQUAL", value="explorer", minScore=3.0)],
        ),
    })
    rules_config = RulesConfig(computeRules=rules)
    strategies_config = StrategiesConfig(strategies=[
        Strategy(key="nba", name="NBA", segment="explorer_campaign",
                 template="Discover {offering}! Your next adventure awaits.",
                 params={"tone": "adventurous"}),
        Strategy(key="nbo", name="NBO", segment="explorer_campaign",
                 strategy="strategic_discovery"),
    ])
    return OntologyEvaluator(ontology, rules_config, strategies_config)


class TestOntologyEvaluator:
    def test_score_quiz_via_evaluator(self, evaluator):
        result = evaluator.score_quiz("archetype", {"q1": "a", "q2": "a"})
        assert result["primary"][0]["value"] == "explorer"

    def test_evaluate_segment_match_with_minscore(self, evaluator):
        is_match, _ = evaluator.evaluate_segment("explorer_campaign", {"archetype": {"value": "explorer", "score": 4.0}})
        assert is_match is True

    def test_evaluate_segment_minscore_miss(self, evaluator):
        is_match, _ = evaluator.evaluate_segment("explorer_campaign", {"archetype": {"value": "explorer", "score": 1.0}})
        assert is_match is False

    def test_resolve_strategy_nba_renders_template(self, evaluator):
        res = evaluator.resolve_strategy("explorer_campaign", "nba", {"offering": "Trekking Gear"})
        assert res["message"] == "Discover Trekking Gear! Your next adventure awaits."
        assert res["params"]["tone"] == "adventurous"

    def test_resolve_strategy_nbo(self, evaluator):
        res = evaluator.resolve_strategy("explorer_campaign", "nbo")
        assert res["strategy"] == "strategic_discovery"

    def test_resolve_unknown_strategy_raises(self, evaluator):
        with pytest.raises(ScoringError, match="no strategy 'next_channel'"):
            evaluator.resolve_strategy("explorer_campaign", "next_channel")

    def test_taxonomy_context_via_evaluator(self, evaluator):
        ctx = evaluator.build_taxonomy_context("explorer_campaign")
        assert any("Driven by discovery" in c for c in ctx)


# ═══════════════════════════════════════════════════════════════
# Generic multi-signal scoring (stateless: caller owns the tally)
# ═══════════════════════════════════════════════════════════════

class TestAggregateAndLabel:
    def test_aggregate_sums_across_sources(self):
        contribs = [
            ScoreContribution(source="assessment", points={"explorer": 2, "sage": 1}),
            ScoreContribution(source="selection", points={"explorer": 1}),
            ScoreContribution(source="acceptance", points={"explorer": 1}),
        ]
        assert aggregate(contribs) == {"explorer": 4, "sage": 1}

    def test_aggregate_empty(self):
        assert aggregate([]) == {}

    def test_label_thresholds(self):
        scoring = ScoringConfig(primaryThreshold=2, secondaryThreshold=1, maxPrimary=1, maxSecondary=2)
        result = label({"explorer": 2, "sage": 1, "hero": 1}, scoring)
        assert [p["value"] for p in result["primary"]] == ["explorer"]
        assert {s["value"] for s in result["secondary"]} == {"sage", "hero"}

    def test_label_uses_name_lookup(self):
        scoring = ScoringConfig(primaryThreshold=1, secondaryThreshold=1, maxPrimary=1, maxSecondary=0)
        result = label({"explorer": 1}, scoring, {"explorer": "Explorer"})
        assert result["primary"][0]["name"] == "Explorer"


class TestProgressiveScoring:
    """The abandoned-cart pattern, generically: an assessment signal plus later
    selection/acceptance signals accumulate to a primary (validated) label."""

    def test_quiz_contribution_then_behavioral_signals(self, evaluator):
        # Action 1: assessment yields a contribution the caller stores.
        c1 = evaluator.quiz_contribution("archetype", {"q1": "a", "q2": "a"})
        assert c1.source == "assessment"
        assert c1.points["explorer"] == 4

        # Actions 2 & 3: caller appends behavioral signals (it owns the tally).
        tally = [
            ScoreContribution(source="selection", points={"explorer": 1}),
            ScoreContribution(source="acceptance", points={"explorer": 1}),
        ]
        # Label the two behavioral confirmations alone (score=2 => primary).
        confirm_scoring = ScoringConfig(primaryThreshold=2, secondaryThreshold=1, maxPrimary=1, maxSecondary=3)
        result = evaluator.label_scores("archetype", tally, scoring=confirm_scoring)
        assert result["primary"][0]["value"] == "explorer"
        assert result["primary"][0]["name"] == "Explorer"  # name from attribute options

    def test_label_scores_defaults_to_quiz_scoring(self, evaluator):
        # No explicit scoring -> uses the attribute's quiz ScoringConfig (primaryThreshold=3).
        result = evaluator.label_scores("archetype", [ScoreContribution(points={"explorer": 3})])
        assert result["primary"][0]["value"] == "explorer"

    def test_label_scores_unknown_attribute_raises(self, evaluator):
        with pytest.raises(ScoringError):
            evaluator.label_scores("ghost", [ScoreContribution(points={"x": 1})])
