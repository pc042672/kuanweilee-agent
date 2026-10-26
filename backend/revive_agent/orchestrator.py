"""
Revive Orchestrator - DS-STAR Inspired Multi-Agent Coordinator

Implements the iterative planning-verification loop:
1. DS-Agent: Gather context, analyze, propose execution plan
2. DE-Agent: Execute plan (SQL/embeddings/LLM)
3. Verifier: Check if result satisfies user query
4. Loop: Refine or backtrack based on verification
"""
import asyncio
import json
import logging
import re
from typing import AsyncGenerator, Any, Optional, Literal
from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

logger = logging.getLogger("ai_cdp.orchestrator")

# Agent-level timeout in seconds (prevents indefinite hangs on LLM failures)
AGENT_TIMEOUT_SECONDS = 120

# Session state keys cleared at the start of each invocation so a new
# user message doesn't see stale results from a prior query on the same thread.
_WORKFLOW_STATE_KEYS = [
    "execution_plan",
    "execution_result",
    "verification",
    "campaign_summary",
    "temp:last_feedback",
]

# Type alias for workflow phases
Phase = Literal["planning", "executing", "verifying", "complete", "error", "waiting"]


def create_state_delta_event(
    author: str,
    phase: Phase,
    iteration: int = 1,
    max_iterations: int = 3,
    execution_plan: Optional[dict] = None,
    execution_result: Optional[dict] = None,
    verification: Optional[dict] = None,
    campaign_summary: Optional[dict] = None,
    error: Optional[str] = None,
    message: Optional[str] = None,
) -> Event:
    """Create an event with state_delta for AG-UI frontend consumption.

    This emits structured state data that the frontend can consume via
    onStateDeltaEvent callback, eliminating the need for text parsing.

    Args:
        author: Event author (agent name)
        phase: Current workflow phase
        iteration: Current iteration number (1-indexed)
        max_iterations: Maximum allowed iterations
        execution_plan: Parsed execution plan dict (optional)
        execution_result: Parsed execution result dict (optional)
        verification: Parsed verification dict (optional)
        campaign_summary: Parsed campaign summary dict (optional)
        error: Error message if in error phase (optional)
        message: Human-readable status message (optional)

    Returns:
        Event with state_delta containing structured workflow state
    """
    state_delta = {
        "workflow": {
            "phase": phase,
            "iteration": iteration,
            "max_iterations": max_iterations,
            "message": message,
        }
    }

    # Add structured data when available
    if execution_plan is not None:
        state_delta["execution_plan"] = execution_plan
    if execution_result is not None:
        state_delta["execution_result"] = execution_result
    if verification is not None:
        state_delta["verification"] = verification
    if campaign_summary is not None:
        state_delta["campaign_summary"] = campaign_summary
    if error is not None:
        state_delta["workflow"]["error"] = error

    # Create event with state_delta in actions
    return Event(
        author=author,
        content=types.Content(
            role="model",
            parts=[types.Part(text=message or f"Phase: {phase}")]
        ),
        actions=EventActions(state_delta=state_delta)
    )


def parse_campaign_summary_from_text(text: str) -> Optional[dict]:
    """Extract campaign_summary JSON from verifier output.

    Looks for the CAMPAIGN_SUMMARY section in the verifier's output.
    """
    if not text or not isinstance(text, str):
        return None

    # Look for CAMPAIGN_SUMMARY section
    campaign_match = re.search(
        r'(?:📊\s*)?CAMPAIGN_SUMMARY:?\s*```(?:json)?\s*(\{.*?\})\s*```',
        text,
        re.DOTALL | re.IGNORECASE
    )
    if campaign_match:
        try:
            return json.loads(campaign_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find any JSON with campaign_title key
    json_match = re.search(r'\{[^{}]*"campaign_title"[^{}]*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def parse_json_from_text(text: str) -> Optional[dict]:
    """Extract JSON object from LLM text output.

    Handles JSON embedded in markdown code blocks or plain text.
    """
    if not text or not isinstance(text, str):
        return None

    # If it's already a dict, return as-is
    if isinstance(text, dict):
        return text

    # Try to find JSON in code blocks first
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find raw JSON object
    json_match = re.search(r'\{[^{}]*"(?:sufficient|status|goal)"[^{}]*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    # Try parsing entire text as JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    return None


class ReviveOrchestrator(BaseAgent):
    """DS-STAR inspired orchestrator with iterative planning-verification loop.

    Coordinates three agents:
    - ds_agent: Data Scientist - gathers context and proposes plans
    - de_agent: Data Engineer - executes plans as SQL
    - verifier: Verifies if results satisfy user query

    The orchestrator runs an iterative loop:
    1. DS-Agent plans
    2. DE-Agent executes
    3. Verifier evaluates
    4. If insufficient: refine and loop (up to max_iterations)
    """

    ds_agent: LlmAgent
    de_agent: LlmAgent
    verifier: LlmAgent
    max_iterations: int = 3

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        ds_agent: LlmAgent,
        de_agent: LlmAgent,
        verifier: LlmAgent,
        max_iterations: int = 3,
        **kwargs,
    ):
        """Initialize the orchestrator with sub-agents.

        Args:
            ds_agent: Data Scientist agent for planning
            de_agent: Data Engineer agent for execution
            verifier: Verifier agent for evaluation
            max_iterations: Maximum refinement iterations (default 3)
        """
        super().__init__(
            name="ReviveOrchestrator",
            ds_agent=ds_agent,
            de_agent=de_agent,
            verifier=verifier,
            max_iterations=max_iterations,
            sub_agents=[ds_agent, de_agent, verifier],
            **kwargs,
        )

    async def _run_agent_with_timeout(
        self,
        agent: LlmAgent,
        ctx: InvocationContext,
        timeout: float = AGENT_TIMEOUT_SECONDS,
    ) -> AsyncGenerator[Event, None]:
        """Run a sub-agent's async generator with a total timeout.

        Raises asyncio.TimeoutError if the entire agent run exceeds
        ``timeout`` seconds (covers LLM hang, network stall, etc.).
        """
        async with asyncio.timeout(timeout):
            async for event in agent.run_async(ctx):
                yield event

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Implement DS-STAR iterative planning-verification loop.

        Flow:
        1. DS-Agent gathers context and proposes plan → state['execution_plan']
        2. DE-Agent executes the plan → state['execution_result']
        3. Verifier evaluates → state['verification']
        4. If sufficient: complete. If not: loop with feedback.

        Emits STATE_DELTA events at each phase transition for frontend consumption.
        """
        logger.info("Starting _run_async_impl")

        for key in _WORKFLOW_STATE_KEYS:
            ctx.session.state[key] = None

        # Read per-site max_iterations from session state (set by middleware/site settings)
        max_iter = ctx.session.state.get("site:max_iterations") or self.max_iterations

        for iteration in range(max_iter):
            iter_num = iteration + 1  # 1-indexed for display

            # Emit iteration start via state_delta
            yield create_state_delta_event(
                author=self.name,
                phase="planning",
                iteration=iter_num,
                max_iterations=max_iter,
                message=f"Iteration {iter_num}/{max_iter} - Planning phase"
            )

            # =================================================================
            # Phase 1: DS-Agent Plans
            # =================================================================
            logger.info("Phase 1: Starting DS-Agent")
            event_count = 0
            try:
                async for event in self._run_agent_with_timeout(self.ds_agent, ctx):
                    event_count += 1
                    yield event
                logger.info("DS-Agent completed with %d events", event_count)
            except asyncio.TimeoutError:
                yield create_state_delta_event(
                    author=self.name,
                    phase="error",
                    iteration=iter_num,
                    max_iterations=max_iter,
                    error=f"DS-Agent timed out after {AGENT_TIMEOUT_SECONDS}s",
                    message=f"DS-Agent timed out after {AGENT_TIMEOUT_SECONDS}s"
                )
                return
            except Exception as e:
                yield create_state_delta_event(
                    author=self.name,
                    phase="error",
                    iteration=iter_num,
                    max_iterations=max_iter,
                    error=str(e),
                    message=f"DS-Agent error: {str(e)}"
                )
                return

            # PRIORITY: Check tool-submitted plan FIRST (DS-Agent's output_key may overwrite with text)
            # The submit_execution_plan tool writes to temp:submitted_plan via ToolContext.state
            plan = None
            submitted_plan = ctx.session.state.get("temp:submitted_plan")
            if submitted_plan:
                plan = submitted_plan
                logger.info("Retrieved plan from ToolContext state: %s", plan[:300] if plan else "None")
                ctx.session.state["execution_plan"] = plan

                # Parse plan and emit via state_delta
                parsed = parse_json_from_text(plan) if isinstance(plan, str) else plan
                yield create_state_delta_event(
                    author=self.name,
                    phase="planning",
                    iteration=iter_num,
                    max_iterations=max_iter,
                    execution_plan=parsed,
                    message="Execution plan received"
                )

            # Fallback to session state if no tool-submitted plan
            if not plan:
                plan = ctx.session.state.get("execution_plan")
                logger.debug("execution_plan from session: %s, type: %s", bool(plan), type(plan))

            logger.debug("Final plan status: %s", bool(plan))

            if not plan:
                # DS-Agent is still gathering context, waiting for user input
                yield create_state_delta_event(
                    author=self.name,
                    phase="waiting",
                    iteration=iter_num,
                    max_iterations=max_iter,
                    message="Gathering context - waiting for user input"
                )
                return

            # Check if plan is a valid JSON execution plan (not just confirmation text)
            # DS-Agent in Phase A asks for confirmation - plan will be text, not JSON
            # DS-Agent in Phase B outputs JSON execution plan after user confirms
            parsed_plan = parse_json_from_text(plan) if isinstance(plan, str) else plan
            if not parsed_plan or "goal" not in parsed_plan:
                # Not a valid execution plan - DS-Agent is still in confirmation phase
                yield create_state_delta_event(
                    author=self.name,
                    phase="waiting",
                    iteration=iter_num,
                    max_iterations=max_iter,
                    message="Plan pending user confirmation"
                )
                return

            # =================================================================
            # Phase 2: DE-Agent Executes
            # =================================================================
            # Emit executing phase start
            yield create_state_delta_event(
                author=self.name,
                phase="executing",
                iteration=iter_num,
                max_iterations=max_iter,
                execution_plan=parsed_plan,
                message="Executing plan - generating SQL"
            )

            try:
                # DE-Agent text output (SQL, explanations) is useful — yield as-is.
                async for event in self._run_agent_with_timeout(self.de_agent, ctx):
                    yield event
            except asyncio.TimeoutError:
                error_result = {"status": "error", "error": f"DE-Agent timed out after {AGENT_TIMEOUT_SECONDS}s"}
                ctx.session.state["execution_result"] = error_result
                yield create_state_delta_event(
                    author=self.name,
                    phase="error",
                    iteration=iter_num,
                    max_iterations=max_iter,
                    execution_plan=parsed_plan,
                    execution_result=error_result,
                    error=f"DE-Agent timed out after {AGENT_TIMEOUT_SECONDS}s",
                    message=f"DE-Agent timed out after {AGENT_TIMEOUT_SECONDS}s"
                )
            except Exception as e:
                error_result = {"status": "error", "error": str(e)}
                ctx.session.state["execution_result"] = error_result
                yield create_state_delta_event(
                    author=self.name,
                    phase="error",
                    iteration=iter_num,
                    max_iterations=max_iter,
                    execution_plan=parsed_plan,
                    execution_result=error_result,
                    error=str(e),
                    message=f"DE-Agent error: {str(e)}"
                )

            result = ctx.session.state.get("execution_result")
            if not result:
                # Execution failed, continue to verification
                error_result = {"status": "error", "error": "DE-Agent did not produce a result"}
                ctx.session.state["execution_result"] = error_result
            else:
                # Parse result if string
                result = parse_json_from_text(result) if isinstance(result, str) else result

            # PRIORITY: Use actual tool result for preview data (LLM may truncate in its summary)
            # The run_sql_preview_tool writes to temp:sql_preview via ToolContext.state
            preview_result = ctx.session.state.get("temp:sql_preview")
            if preview_result:
                logger.info("Using ToolContext preview: %s rows", preview_result.get("row_count"))
                # Merge preview data into result, preserving full data
                if result and isinstance(result, dict):
                    result["preview"] = {
                        "row_count": preview_result.get("row_count", 0),
                        "sample": preview_result.get("data", [])
                    }
                    result["sql"] = preview_result.get("sql", result.get("sql", ""))
                    result["status"] = "success" if preview_result.get("success") else "error"
                    if not preview_result.get("success"):
                        result["error"] = preview_result.get("error")

            # Emit execution result via state_delta
            yield create_state_delta_event(
                author=self.name,
                phase="executing",
                iteration=iter_num,
                max_iterations=max_iter,
                execution_plan=parsed_plan,
                execution_result=result,
                message="Execution complete - SQL generated"
            )

            # =================================================================
            # Phase 3: Verifier Evaluates
            # =================================================================
            # Emit verifying phase start
            yield create_state_delta_event(
                author=self.name,
                phase="verifying",
                iteration=iter_num,
                max_iterations=max_iter,
                execution_plan=parsed_plan,
                execution_result=result,
                message="Verifying result"
            )

            try:
                # Verifier emits text with VERIFICATION + CAMPAIGN_SUMMARY blocks.
                async for event in self._run_agent_with_timeout(self.verifier, ctx):
                    yield event
            except asyncio.TimeoutError:
                yield create_state_delta_event(
                    author=self.name,
                    phase="error",
                    iteration=iter_num,
                    max_iterations=max_iter,
                    execution_plan=parsed_plan,
                    execution_result=result,
                    error=f"Verifier timed out after {AGENT_TIMEOUT_SECONDS}s",
                    message=f"Verifier timed out after {AGENT_TIMEOUT_SECONDS}s"
                )
                continue
            except Exception as e:
                yield create_state_delta_event(
                    author=self.name,
                    phase="error",
                    iteration=iter_num,
                    max_iterations=max_iter,
                    execution_plan=parsed_plan,
                    execution_result=result,
                    error=str(e),
                    message=f"Verifier error: {str(e)}"
                )
                # Continue to next iteration on verifier error
                continue

            verification_raw = ctx.session.state.get("verification")
            verification = parse_json_from_text(verification_raw) if verification_raw else None

            # Extract campaign_summary from verifier text output
            campaign_summary = parse_campaign_summary_from_text(verification_raw) if verification_raw else None
            if campaign_summary:
                logger.info("Extracted campaign_summary: %s", list(campaign_summary.keys()))
                ctx.session.state["campaign_summary"] = campaign_summary

            # Check if task is complete
            if verification:
                sufficient = verification.get("sufficient", False)
                action = verification.get("action", "complete")

                if sufficient or action == "complete":
                    # Success - task complete
                    yield create_state_delta_event(
                        author=self.name,
                        phase="complete",
                        iteration=iter_num,
                        max_iterations=max_iter,
                        execution_plan=parsed_plan,
                        execution_result=result,
                        verification=verification,
                        campaign_summary=campaign_summary,
                        message="Task completed successfully!"
                    )
                    # Also emit escalate to signal completion
                    yield Event(
                        author=self.name,
                        content=types.Content(
                            role="model",
                            parts=[types.Part(text="")]
                        ),
                        actions=EventActions(escalate=True)
                    )
                    return

                # =============================================================
                # Phase 4: Route Decision (refine or backtrack)
                # =============================================================
                feedback = verification.get("feedback", "")
                ctx.session.state["temp:last_feedback"] = feedback

                # Emit verification result with routing decision
                yield create_state_delta_event(
                    author=self.name,
                    phase="verifying",
                    iteration=iter_num,
                    max_iterations=max_iter,
                    execution_plan=parsed_plan,
                    execution_result=result,
                    verification=verification,
                    message=f"{'Backtracking' if action == 'backtrack' else 'Refining'}: {feedback}"
                )

                if action == "backtrack":
                    for key in _WORKFLOW_STATE_KEYS:
                        ctx.session.state[key] = None

        # Max iterations reached
        yield create_state_delta_event(
            author=self.name,
            phase="error",
            iteration=max_iter,
            max_iterations=max_iter,
            error=f"Max iterations ({max_iter}) reached",
            message=f"Max iterations ({max_iter}) reached. Please refine your request or provide more context."
        )
