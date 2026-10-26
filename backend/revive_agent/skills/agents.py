"""Skill-layer sub-agents (currently unwired — the IntentRouter was removed).

Each agent owns one task type; tool lists come from the tools registry,
which wraps mutating tools in a per-site HITL confirmation policy
(guardrail_level: strict default). DS-STAR (ReviveOrchestrator) is the
root agent; these specialists are kept for a future routing mechanism.
"""

from google.adk.agents import LlmAgent

from revive_agent.agent import MODEL
from tools_registry import tools_for

_PLAN_VS_SKILL = """
The marketing plan states WHAT to execute and WHY (channel choice + rationale,
target segment, KPI linkage). Skills encode HOW — which CDP API/tool realizes
it. Always present the WHAT/WHY to the user before executing the HOW.
Before any mutation, show the proposed change as a clear before/after diff and
wait for the user's confirmation if asked to confirm.
"""

strategy_agent = LlmAgent(
    name="StrategyAgent",
    model=MODEL,
    description=(
        "Campaign strategy advisor: resolves per-segment message strategies "
        "(NBA/NBO), analyzes brand identity from a website, classifies content "
        "against the Jungian persona taxonomy. Use for 'what should we say/offer "
        "to segment X', brand analysis, persona/archetype questions."
    ),
    instruction=(
        "You are the campaign strategy advisor of an AI CDP.\n"
        "- resolve_strategy_tool renders the configured strategy/message for a segment\n"
        "- analyze_brand_tool extracts brand identity from a URL\n"
        "- classify_persona_tool maps content to Jungian archetypes\n"
        "Answer in business language; cite which segment/strategy config you used."
        + _PLAN_VS_SKILL
    ),
    tools=tools_for("strategy"),
)

rule_agent = LlmAgent(
    name="RuleAgent",
    model=MODEL,
    description=(
        "Compute-rule editor: views, creates, updates, deletes the rules that "
        "compute attribute values (SQL rules, quiz scoring, labeling rules). "
        "Use for 'create/change/delete a rule', scoring threshold changes."
    ),
    instruction=(
        "You manage compute rules (how attributes get their values).\n"
        "Read with get_attribute_tool / get_ontology_tool; audit with "
        "audit_ontology_tool. Mutate ONLY via upsert_rule_tool / delete_rule_tool.\n"
        "Before mutating: show the user the exact before/after change. "
        "Rules reference ontology attributes and datasources BY KEY — verify the "
        "keys exist first; integrity validation rejects bad references."
        + _PLAN_VS_SKILL
    ),
    tools=tools_for("rule"),
)

ontology_agent = LlmAgent(
    name="OntologyAgent",
    model=MODEL,
    description=(
        "Ontology editor: views and edits the semantic layer — datasources "
        "(tables), attributes, segments. Use for 'add a table/attribute/segment', "
        "'change segment conditions', ontology audits."
    ),
    instruction=(
        "You manage the ontology (structure layer): datasource, attribute and "
        "segment nodes.\n"
        "Read with get_ontology_tool / get_attribute_tool; check integrity with "
        "audit_ontology_tool. Mutate ONLY via upsert_ontology_node_tool / "
        "delete_ontology_node_tool.\n"
        "Before mutating: show the exact before/after diff. Deletes are refused "
        "while rules or strategies still reference the node."
        + _PLAN_VS_SKILL
    ),
    tools=tools_for("ontology"),
)


skill_executor = LlmAgent(
    name="SkillExecutor",
    model=MODEL,
    description=(
        "Execution agent: runs approved actions through the connected CDP "
        "system — set up or schedule a campaign, create segmentation, set "
        "real-time score/behavior rules; also exports audiences to CSV and "
        "builds charts from result data. Use when the user wants to EXECUTE "
        "or SEND something, export data, or chart results."
    ),
    instruction=(
        "You execute approved marketing actions via the connected CDP system.\n"
        "- execute_action hands a MarketingPlan to the CDP connector "
        "(currently dry-run until the real API/MCP is configured) — build the "
        "plan_json with: goal, kpi, segmentation (taxonomy segment_key OR "
        "behavioral criteria), audience, analysis_evidence, strategy, channel "
        "(edm|sms|web_popup) and channel_rationale\n"
        "- audience_export materializes an audience SQL to CSV\n"
        "- chart_generation builds a chart spec from result rows\n"
        "- get_taxonomy / list_campaigns read from the connected CDP\n"
        "Always state WHAT will be executed and WHY (channel rationale, KPI) "
        "before dispatching; report the dry-run/submitted status honestly."
        + _PLAN_VS_SKILL
    ),
    tools=tools_for("skill"),
)
