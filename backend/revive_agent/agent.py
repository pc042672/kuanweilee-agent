"""
Revive Agent - ADK Web Entry Point

DS-STAR inspired multi-agent architecture for Greenplum SQL generation.
- DS-Agent (Planner): Gathers context, analyzes scenarios, proposes execution plans
- DE-Agent (Executor): Implements plans as SQL, validates and executes
- Verifier: Evaluates if results satisfy the user query
- Orchestrator: Coordinates the iterative planning-verification loop
"""
import sys
from pathlib import Path

# Add 'backend' directory to Python path for imports
# Path: backend/revive_agent/agent.py -> parent.parent = backend/
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import logging

from google.genai import types
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from revive_agent.instructions import (
    DS_AGENT_INSTRUCTION,
    de_agent_instruction,
    verifier_instruction,
)
from tools_registry import tools_for

# =============================================================================
# MODEL CONFIGURATION (Don't change without updating plan file!)
# =============================================================================
# Model: gemini-3-flash-preview (Gemini 3 Flash Preview)
# - Max Input: 1M tokens, Max Output: 64K tokens
# - Knowledge Cutoff: January 2025
# - Reference: https://ai.google.dev/gemini-api/docs/gemini-3

MODEL_NAME = "gemini-3-flash-preview"

# Retry configuration for resilience against transient errors
RETRY_CONFIG = types.HttpRetryOptions(
    attempts=5,
    exp_base=7,
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504],
)

# Configured model with retry support
MODEL = Gemini(model=MODEL_NAME, retry_options=RETRY_CONFIG)

# =============================================================================
# DS-AGENT (Data Scientist - Semantic Labeling)
# =============================================================================
# Analyzes customer segment requests, matches to labels, confirms with user
ds_agent = LlmAgent(
    name="DSAgent",
    model=MODEL,
    description="Data Scientist Agent - Semantic labeling and brand analysis",
    instruction=DS_AGENT_INSTRUCTION,
    tools=[
        *tools_for("ds"),
        # Long-term memory recall (auto-injects relevant past facts)
        PreloadMemoryTool(),
    ],
    output_key="execution_plan"
)


# =============================================================================
# DE-AGENT (Data Engineer - Executor)
# =============================================================================
# Implements execution plans as SQL, validates and executes
de_agent = LlmAgent(
    name="DEAgent",
    model=MODEL,
    description="Data Engineer Agent - Executes plans and generates SQL",
    instruction=de_agent_instruction,
    tools=tools_for("de"),
    output_key="execution_result"
)

# =============================================================================
# VERIFIER AGENT
# =============================================================================
# Evaluates if execution result satisfies user query
verifier_agent = LlmAgent(
    name="Verifier",
    model=MODEL,
    description="Verifies if execution result satisfies user query and generates campaign summary",
    instruction=verifier_instruction,
    output_key="verification",
)

# =============================================================================
# ROOT AGENT SELECTION
# =============================================================================
# DS-STAR Orchestrator coordinates the iterative planning-verification loop
from revive_agent.orchestrator import ReviveOrchestrator

_memory_logger = logging.getLogger("ai_cdp.memory")


async def _save_session_to_memory(callback_context):
    """Distill the finished run into long-term memory. Never breaks chat."""
    try:
        await callback_context.add_session_to_memory()
    except ValueError:
        pass  # no memory service configured (bare Runner / unit tests)
    except Exception:
        _memory_logger.exception("memory ingestion failed")
    return None


revive_orchestrator = ReviveOrchestrator(
    ds_agent=ds_agent,
    de_agent=de_agent,
    verifier=verifier_agent,
    max_iterations=3,
    after_agent_callback=_save_session_to_memory,
    description=(
        "DS-STAR data-analysis workflow: finds and segments customers via "
        "text-to-SQL, builds audiences, and produces an evidence-backed "
        "marketing plan. The default path for any data question or analysis."
    ),
)

# ADK web requires the root agent to be named 'root_agent'
root_agent = revive_orchestrator
