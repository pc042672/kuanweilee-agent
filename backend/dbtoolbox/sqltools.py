"""Declarative parameterized SQL tools (genai-toolbox style).

A SQLToolDef is a named, described SELECT statement with typed parameters,
stored per-site in site_configs (config_type='sql_tools'):

    {"tools": [{
        "name": "hotels_by_name",
        "description": "Search hotels by name fragment",
        "statement": "SELECT * FROM data.hotels WHERE name ILIKE :name",
        "parameters": [{"name": "name", "type": "string", "description": "..."}]
    }]}

Values bind via SQLAlchemy named params (driver-level, injection-safe).
Statements are policy-validated at load time and again at execution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from dbtoolbox.policy import SecurityPolicy, validate_sql
from dbtoolbox.service import QueryService

logger = logging.getLogger("ai_cdp.dbtoolbox.sqltools")

_PARAM_TYPES = {
    "string": str,
    "integer": int,
    "float": float,
    "boolean": bool,
}


@dataclass(frozen=True)
class ParamDef:
    name: str
    type: str = "string"  # string | integer | float | boolean
    description: str = ""
    required: bool = True
    default: Any = None


@dataclass(frozen=True)
class SQLToolDef:
    name: str
    description: str
    statement: str  # named :params only — no string interpolation
    parameters: Tuple[ParamDef, ...] = field(default_factory=tuple)


def parse_tool_defs(config_data: dict, policy: SecurityPolicy) -> List[SQLToolDef]:
    """Parse and policy-validate tool definitions; invalid entries are skipped loudly."""
    tools: List[SQLToolDef] = []
    for raw in (config_data or {}).get("tools", []):
        try:
            params = tuple(
                ParamDef(
                    name=p["name"],
                    type=p.get("type", "string"),
                    description=p.get("description", ""),
                    required=p.get("required", True),
                    default=p.get("default"),
                )
                for p in raw.get("parameters", [])
            )
            tool = SQLToolDef(
                name=raw["name"],
                description=raw.get("description", ""),
                statement=raw["statement"],
                parameters=params,
            )
        except (KeyError, TypeError) as e:
            logger.error("Invalid sql_tool definition skipped: %s (%s)", raw, e)
            continue
        result = validate_sql(tool.statement, policy)
        if not result.valid:
            logger.error(
                "sql_tool '%s' rejected by policy (%s): %s",
                tool.name, result.error_type, result.error,
            )
            continue
        tools.append(tool)
    return tools


def load_sql_tools(site_id: int, policy: SecurityPolicy) -> List[SQLToolDef]:
    """Load the site's declarative SQL tools from site_configs."""
    try:
        from db import get_engine
        from sqlalchemy import text

        engine = get_engine()
        if engine is None:
            return []
        with engine.connect() as conn:
            config_data = conn.execute(
                text(
                    "SELECT config_data FROM site_configs "
                    "WHERE site_id = :sid AND config_type = 'sql_tools'"
                ),
                {"sid": site_id},
            ).scalar()
        if not config_data:
            return []
        return parse_tool_defs(config_data, policy)
    except Exception as e:
        logger.warning("sql_tools load failed for site %s: %s", site_id, e)
        return []


def coerce_args(tool: SQLToolDef, args: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and type-coerce arguments against the tool's ParamDefs.

    Raises ValueError on missing required params or uncoercible values.
    Unknown args are dropped (never reach the statement).
    """
    coerced: Dict[str, Any] = {}
    for p in tool.parameters:
        if p.name in args and args[p.name] is not None:
            caster = _PARAM_TYPES.get(p.type, str)
            try:
                value = args[p.name]
                coerced[p.name] = value if isinstance(value, caster) else caster(value)
            except (ValueError, TypeError):
                raise ValueError(f"Parameter '{p.name}' must be of type {p.type}")
        elif p.default is not None:
            coerced[p.name] = p.default
        elif p.required:
            raise ValueError(f"Missing required parameter '{p.name}'")
    return coerced


def run_sql_tool(
    service: QueryService, tool: SQLToolDef, args: Dict[str, Any],
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute a declarative tool with validated, bound parameters."""
    from dbtoolbox.errors import PolicyViolation, categorize_dbapi_error

    try:
        params = coerce_args(tool, args)
    except ValueError as e:
        return {"success": False, "error": str(e), "error_type": "invalid_arguments"}
    try:
        data = service.execute(tool.statement, params=params, limit=limit)
        return {
            "success": True,
            "tool": tool.name,
            "data": data,
            "row_count": len(data),
        }
    except Exception as e:
        error_type = e.error_type if isinstance(e, PolicyViolation) else categorize_dbapi_error(e)
        return {"success": False, "tool": tool.name, "error": str(e), "error_type": error_type}
