"""ADK Plugins for AI-CDP agent system.

Plugins apply globally across all agents at the Runner level,
providing defense-in-depth guardrails and observability.
"""
import logging
import re
import time
from typing import Any, Optional

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.tools import BaseTool, ToolContext

logger = logging.getLogger("ai_cdp.plugins")

# OpenTelemetry tracer (lazy-init, None if tracing disabled)
_tracer = None


def _get_tracer():
    global _tracer
    if _tracer is None:
        try:
            import settings
            if settings.ENABLE_CLOUD_TRACE:
                from opentelemetry import trace
                _tracer = trace.get_tracer("ai-cdp")
            else:
                _tracer = False  # Disabled, don't retry
        except Exception:
            _tracer = False
    return _tracer if _tracer else None

# Regex to extract table names from FROM/JOIN clauses
# Matches quoted and unquoted refs: FROM schema.table / FROM "schema"."table".
# Quoted forms MUST be covered — the model organically bypassed an
# unquoted-only allowlist by writing FROM "report"."smb_abandon_list".
_TABLE_REF_PATTERN = re.compile(
    r'(?:FROM|JOIN)\s+("?[a-zA-Z_][a-zA-Z0-9_]*"?(?:\."?[a-zA-Z_][a-zA-Z0-9_]*"?)*)',
    re.IGNORECASE,
)
# Regex to extract CTE aliases (WITH name AS ...)
_CTE_ALIAS_PATTERN = re.compile(
    r'\bWITH\s+(\w+)\s+AS\b|\,\s*(\w+)\s+AS\s*\(',
    re.IGNORECASE,
)

# SQL patterns that are never allowed through agent tools
_BLOCKED_SQL_PATTERNS = [
    (re.compile(r'\bDROP\b', re.IGNORECASE), "DROP"),
    (re.compile(r'\bTRUNCATE\b', re.IGNORECASE), "TRUNCATE"),
    (re.compile(r'\bDELETE\b', re.IGNORECASE), "DELETE"),
    (re.compile(r'\bALTER\b', re.IGNORECASE), "ALTER"),
    (re.compile(r'\bINSERT\b', re.IGNORECASE), "INSERT"),
    (re.compile(r'\bUPDATE\b', re.IGNORECASE), "UPDATE"),
    (re.compile(r'\bCREATE\b', re.IGNORECASE), "CREATE"),
    (re.compile(r'\bGRANT\b', re.IGNORECASE), "GRANT"),
    (re.compile(r'\bREVOKE\b', re.IGNORECASE), "REVOKE"),
    (re.compile(r'\bCOPY\b', re.IGNORECASE), "COPY"),
]

# Tools that execute SQL and need guardrailing
_SQL_TOOL_NAMES = {"dry_run_sql_tool", "run_sql_preview_tool", "audience_export_tool"}


def _extract_sql(tool_args: dict) -> str:
    """SQL arg name differs per tool: sql_query (dry-run/preview) vs sql (export)."""
    return tool_args.get("sql_query") or tool_args.get("sql", "")


class ServiceGatingPlugin(BasePlugin):
    """Blocks tools whose required external service is unconfigured for the site.

    Agents are module-level singletons shared across sites, so per-site tool
    availability must be a runtime check at the tool boundary — this plugin
    applies App-wide (both /ag-ui and /api/chat/stream paths).
    """

    def __init__(self):
        super().__init__(name="service_gating")

    async def before_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
    ) -> Optional[dict]:
        from tools_registry import get_registry

        spec = get_registry().get(tool.name)
        required = spec.required_services if spec else ()
        if not required:
            return None

        from revive_agent.tools._infra import get_site_id
        from services.credentials import is_configured, service_not_configured_result

        site_id = get_site_id()
        for service in required:
            if not is_configured(site_id, service):
                logger.warning(
                    "[SERVICE_GATING] blocked %s for site=%s — '%s' not configured",
                    tool.name, site_id, service,
                )
                return service_not_configured_result(tool.name, service)
        return None


class SQLSafetyPlugin(BasePlugin):
    """Plugin that enforces read-only SQL policy across all agents.

    Intercepts SQL tool calls and blocks any non-SELECT/EXPLAIN queries.
    This is defense-in-depth that cannot be bypassed by prompt injection.
    """

    def __init__(self):
        super().__init__(name="sql_safety")

    async def before_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
    ) -> Optional[dict]:
        if tool.name not in _SQL_TOOL_NAMES:
            return None

        sql = _extract_sql(tool_args)
        sql_upper = sql.strip().upper()

        # Enforce SELECT/EXPLAIN only
        if not (sql_upper.startswith("SELECT") or sql_upper.startswith("EXPLAIN")
                or sql_upper.startswith("WITH")):
            logger.warning(f"SQL Safety: blocked non-SELECT query: {sql[:100]}")
            return {
                "valid": False,
                "success": False,
                "error": "Only SELECT, EXPLAIN, and WITH (CTE) queries are permitted",
                "error_type": "policy_violation",
                "suggestion": "Rewrite as a SELECT query",
            }

        # Check for blocked patterns (e.g., subqueries with DELETE)
        for pattern, name in _BLOCKED_SQL_PATTERNS:
            if pattern.search(sql):
                logger.warning(f"SQL Safety: blocked {name} in query: {sql[:100]}")
                return {
                    "valid": False,
                    "success": False,
                    "error": f"Policy violation: {name} statements are not allowed",
                    "error_type": "policy_violation",
                    "suggestion": "Only SELECT queries are permitted for analysis",
                }

        # Check table allowlist from ontology DataSource nodes
        try:
            from revive_agent.tools._infra import get_config
            allowed = get_config().get_allowed_tables()
            if allowed:
                referenced = {t.replace('"', '') for t in _TABLE_REF_PATTERN.findall(sql)}
                # Exclude CTE aliases (not real tables)
                cte_aliases = {m[0] or m[1] for m in _CTE_ALIAS_PATTERN.findall(sql)}
                referenced -= cte_aliases
                unauthorized = referenced - allowed
                if unauthorized:
                    logger.warning(f"SQL Safety: unauthorized tables: {unauthorized}")
                    return {
                        "valid": False,
                        "success": False,
                        "error": f"Table access denied: {', '.join(sorted(unauthorized))}. Only ontology-defined data sources are permitted.",
                        "error_type": "table_authorization",
                    }
        except Exception as e:
            logger.debug("SQL Safety: table allowlist check skipped — %s", e)

        return None


class LoggingPlugin(BasePlugin):
    """Plugin that provides structured logging for agent and tool lifecycle.

    Logs agent start/end with timing, and tool calls with arguments.
    OTel spans stored on plugin instance (not session state) to avoid
    serialization issues with DatabaseSessionService.
    """

    def __init__(self):
        super().__init__(name="logging")
        self._spans: dict[str, Any] = {}  # keyed by context id, non-serializable

    async def before_run_callback(
        self, *, invocation_context: InvocationContext
    ) -> None:
        invocation_context.session.state["temp:run_start_time"] = time.time()
        tracer = _get_tracer()
        if tracer:
            span = tracer.start_span("orchestrator.run")
            span.set_attribute("session.id", invocation_context.session.id)
            self._spans[f"run:{invocation_context.session.id}"] = span
        logger.info(
            "[ORCHESTRATOR] Invocation started | session=%s",
            invocation_context.session.id,
        )
        return None

    async def after_run_callback(
        self, *, invocation_context: InvocationContext
    ) -> None:
        start = invocation_context.session.state.get("temp:run_start_time", 0)
        duration = time.time() - start
        span_key = f"run:{invocation_context.session.id}"
        span = self._spans.pop(span_key, None)
        if span:
            span.set_attribute("duration_seconds", duration)
            span.end()
        logger.info(
            "[ORCHESTRATOR] Invocation completed | session=%s duration=%.2fs",
            invocation_context.session.id,
            duration,
        )

    async def before_agent_callback(
        self, *, agent: BaseAgent, callback_context: CallbackContext
    ) -> None:
        callback_context.state[f"temp:agent_start_{agent.name}"] = time.time()
        tracer = _get_tracer()
        if tracer:
            span = tracer.start_span(f"agent.{agent.name}")
            self._spans[f"agent:{agent.name}:{id(callback_context)}"] = span
        logger.info("[%s] Agent started", agent.name)
        return None

    async def after_agent_callback(
        self, *, agent: BaseAgent, callback_context: CallbackContext
    ) -> None:
        start = callback_context.state.get(f"temp:agent_start_{agent.name}", 0)
        duration = time.time() - start
        span = self._spans.pop(f"agent:{agent.name}:{id(callback_context)}", None)
        if span:
            span.set_attribute("duration_seconds", duration)
            span.end()
        logger.info("[%s] Agent completed | duration=%.2fs", agent.name, duration)
        return None

    async def before_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
    ) -> Optional[dict]:
        tool_context.state["temp:tool_start_time"] = time.time()
        tracer = _get_tracer()
        if tracer:
            span = tracer.start_span(f"tool.{tool.name}")
            self._spans[f"tool:{id(tool_context)}"] = span
        args_summary = {k: str(v)[:200] for k, v in tool_args.items()}
        logger.info("[TOOL] %s called | args=%s", tool.name, args_summary)
        return None

    async def after_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        result: dict,
    ) -> Optional[dict]:
        start = tool_context.state.get("temp:tool_start_time", 0)
        duration = time.time() - start
        result_keys = list(result.keys()) if isinstance(result, dict) else type(result).__name__
        span = self._spans.pop(f"tool:{id(tool_context)}", None)
        if span:
            span.set_attribute("duration_seconds", duration)
            span.set_attribute("tool.name", tool.name)
            span.end()
        logger.info(
            "[TOOL] %s completed | duration=%.2fs keys=%s",
            tool.name, duration, result_keys,
        )

        # Log SQL tool executions to action_executions table
        if tool.name in _SQL_TOOL_NAMES:
            try:
                from config.action_log import log_action
                from db import get_engine
                from revive_agent.tools._infra import get_site_id
                engine = get_engine()
                if engine:
                    site_id = get_site_id()
                    status = "succeeded" if isinstance(result, dict) and result.get("valid", result.get("success", True)) else "failed"
                    error_msg = result.get("error") if isinstance(result, dict) else None
                    log_action(
                        engine, site_id=site_id, action_type=f"tool:{tool.name}",
                        request_data={"sql": _extract_sql(tool_args)[:500]},
                        response_data={"keys": result_keys} if isinstance(result_keys, list) else {},
                        status=status, error_message=error_msg,
                    )
            except Exception:
                pass

        return None

    async def after_model_callback(
        self, *, callback_context: CallbackContext, llm_response
    ) -> Optional[Any]:
        """Track token usage from model responses."""
        try:
            usage = getattr(llm_response, 'usage_metadata', None)
            if usage:
                input_tokens = getattr(usage, 'prompt_token_count', 0) or 0
                output_tokens = getattr(usage, 'candidates_token_count', 0) or 0
                total = input_tokens + output_tokens
                logger.info(
                    "[TOKENS] input=%d output=%d total=%d",
                    input_tokens, output_tokens, total,
                )
                callback_context.state["temp:last_input_tokens"] = input_tokens
                callback_context.state["temp:last_output_tokens"] = output_tokens
                # Accumulate per-invocation totals
                callback_context.state["temp:total_input_tokens"] = (
                    callback_context.state.get("temp:total_input_tokens", 0) + input_tokens
                )
                callback_context.state["temp:total_output_tokens"] = (
                    callback_context.state.get("temp:total_output_tokens", 0) + output_tokens
                )
                # Attach token counts to the active agent span (if any)
                for key, span in self._spans.items():
                    if key.startswith("agent:"):
                        span.set_attribute("tokens.input", input_tokens)
                        span.set_attribute("tokens.output", output_tokens)
                        break
        except Exception as e:
            logger.debug("[TOKENS] Failed to extract usage: %s", e)
        return None


# PII patterns for model guard (credit card, SSN, email, phone)
_PII_PATTERNS = [
    (re.compile(r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b'), "credit_card"),
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), "ssn"),
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), "email"),
    (re.compile(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'), "phone"),
    (re.compile(r'\b[A-Z]\d{9}\b'), "passport"),
]


def _redact_pii(text: str) -> tuple[str, list[str]]:
    """Replace PII patterns with [REDACTED]. Returns (redacted_text, detected_types)."""
    detected = []
    for pattern, pii_type in _PII_PATTERNS:
        if pattern.search(text):
            detected.append(pii_type)
            text = pattern.sub("[REDACTED]", text)
    return text, detected


class ModelGuardPlugin(BasePlugin):
    """Optional plugin for regulated industries (financial, healthcare).

    Scans LLM input/output for PII and redacts before processing.
    Enable via ENABLE_MODEL_GUARD=true env var.
    """

    def __init__(self):
        super().__init__(name="model_guard")

    async def before_model_callback(
        self, *, callback_context: CallbackContext, llm_request
    ) -> Optional[Any]:
        """Scan user messages for PII before sending to model."""
        try:
            if hasattr(llm_request, 'contents') and llm_request.contents:
                for content in llm_request.contents:
                    if hasattr(content, 'parts'):
                        for part in content.parts:
                            if hasattr(part, 'text') and part.text:
                                redacted, detected = _redact_pii(part.text)
                                if detected:
                                    logger.warning(
                                        "[MODEL_GUARD] PII detected in input: %s",
                                        detected,
                                    )
                                    part.text = redacted
        except Exception as e:
            logger.debug("[MODEL_GUARD] Input scan error: %s", e)
        return None

    async def after_model_callback(
        self, *, callback_context: CallbackContext, llm_response
    ) -> Optional[Any]:
        """Scan model response for PII before returning to user."""
        try:
            if hasattr(llm_response, 'content') and llm_response.content:
                if hasattr(llm_response.content, 'parts'):
                    for part in llm_response.content.parts:
                        if hasattr(part, 'text') and part.text:
                            redacted, detected = _redact_pii(part.text)
                            if detected:
                                logger.warning(
                                    "[MODEL_GUARD] PII detected in output: %s",
                                    detected,
                                )
                                part.text = redacted
        except Exception as e:
            logger.debug("[MODEL_GUARD] Output scan error: %s", e)
        return None
