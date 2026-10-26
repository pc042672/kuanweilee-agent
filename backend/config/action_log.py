"""Action execution logger — records scoring, segment, and NBA/NBO actions."""

import json
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def log_action(
    engine,
    site_id: int,
    action_type: str,
    target_node_key: Optional[str] = None,
    request_data: Optional[Dict[str, Any]] = None,
    response_data: Optional[Dict[str, Any]] = None,
    status: str = "succeeded",
    error_message: Optional[str] = None,
    executed_by: Optional[int] = None,
    started_at: Optional[float] = None,
) -> None:
    """Record an action execution. Fire-and-forget — never raises."""
    try:
        from sqlalchemy import text

        completed_at = "NOW()"
        params = {
            "site_id": site_id,
            "action_type": action_type,
            "target_node_key": target_node_key,
            "request_json": json.dumps(request_data) if request_data else None,
            "response_json": json.dumps(response_data) if response_data else None,
            "execution_status": status,
            "error_message": error_message,
            "executed_by": executed_by,
        }

        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO action_executions "
                    "(site_id, action_type, target_node_key, request_json, response_json, "
                    "execution_status, error_message, executed_by, completed_at) "
                    "VALUES (:site_id, :action_type, :target_node_key, :request_json, :response_json, "
                    ":execution_status, :error_message, :executed_by, NOW())"
                ),
                params,
            )
    except Exception as e:
        logger.warning("Failed to log action execution: %s", e)
