"""Tests for the external-action connector layer."""

import asyncio

import pytest

from backend.services.external_actions import (
    DryRunAdapter,
    ExternalAction,
    ExternalActionAdapter,
    ExecutionRecord,
    MarketingPlan,
    SegmentationBasis,
    get_adapter,
    register_adapter,
)


def _plan(**over):
    base = dict(
        goal="recover abandoned carts",
        segmentation=SegmentationBasis(basis="taxonomy", segment_key="hero_campaign"),
        channel="edm",
    )
    base.update(over)
    return MarketingPlan(**base)


def test_marketingplan_taxonomy_roundtrip():
    plan = _plan()
    dumped = plan.model_dump(mode="json")
    assert MarketingPlan(**dumped).segmentation.segment_key == "hero_campaign"


def test_marketingplan_behavioral():
    plan = _plan(segmentation=SegmentationBasis(
        basis="behavioral", behavior_criteria="cart_abandoned in last 24h"))
    assert plan.segmentation.behavior_criteria.startswith("cart_abandoned")


@pytest.mark.parametrize("action_type", [
    "setup_campaign", "schedule_campaign", "setup_segmentation",
    "setup_score_rule", "setup_behavior_rule",
])
def test_all_action_types_dry_run(action_type):
    action = ExternalAction(action_type=action_type, plan=_plan())
    record = asyncio.run(DryRunAdapter().execute(action))
    assert record.status == "dry_run"
    assert record.adapter == "dry_run"


def test_registry_fallback_to_dry_run():
    assert get_adapter(site_id=999, name="nonexistent").name == "dry_run"


def test_registry_site_scoped_resolution():
    class FakeAdapter(ExternalActionAdapter):
        name = "fake_cdp"
        async def execute(self, action):
            return ExecutionRecord(status="submitted", adapter=self.name,
                                   external_ref="ext-1")

    register_adapter(FakeAdapter(), site_id=42)
    resolved = get_adapter(site_id=42, name="fake_cdp")
    assert resolved.name == "fake_cdp"
    # Different site falls back
    assert get_adapter(site_id=7, name="fake_cdp").name == "dry_run"


def test_get_taxonomy_stub_uses_ontology():
    from backend.services.external_actions import get_taxonomy_stub

    tax = get_taxonomy_stub(site_id=1)
    assert tax["source"] == "internal_ontology"
    assert any("campaign" in k for k in tax["segments"])
