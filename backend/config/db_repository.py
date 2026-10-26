"""Database-backed ontology repository.

Implements OntologyRepository Protocol using SQLAlchemy for PostgreSQL.
Selected automatically when DATABASE_URL is set (see loader.py).
"""

import json
import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .schemas import UnifiedOntologyConfig

logger = logging.getLogger(__name__)


def _compute_diff(before: Optional[dict], after: dict) -> dict:
    """Compute field-level diff between two config snapshots."""
    if before is None:
        return {"added": list(after.get("nodes", {}).keys())}
    before_nodes = before.get("nodes", {})
    after_nodes = after.get("nodes", {})
    all_keys = set(list(before_nodes.keys()) + list(after_nodes.keys()))
    added = [k for k in all_keys if k not in before_nodes]
    removed = [k for k in all_keys if k not in after_nodes]
    changed = {}
    for k in all_keys:
        if k in before_nodes and k in after_nodes and before_nodes[k] != after_nodes[k]:
            changed[k] = {"before": before_nodes[k], "after": after_nodes[k]}
    result = {}
    if added:
        result["added"] = added
    if removed:
        result["removed"] = removed
    if changed:
        result["changed"] = changed
    return result


class DbOntologyRepository:
    """PostgreSQL implementation of OntologyRepository Protocol."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def load(self, site_id: str = "default") -> UnifiedOntologyConfig:
        site_id_int = self._resolve_site_id(site_id)
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT config_data FROM site_configs "
                    "WHERE site_id = :site_id AND config_type = 'ontology'"
                ),
                {"site_id": site_id_int},
            ).fetchone()

        if row is None:
            raise FileNotFoundError(
                f"Ontology config not found for site_id={site_id}"
            )

        data = row[0]
        if isinstance(data, str):
            data = json.loads(data)
        return UnifiedOntologyConfig(**data)

    def save(
        self,
        config: UnifiedOntologyConfig,
        site_id: str = "default",
        changed_by: Optional[int] = None,
    ) -> None:
        site_id_int = self._resolve_site_id(site_id)
        data_json = json.dumps(config.model_dump())

        with self._engine.begin() as conn:
            if changed_by:
                old_row = conn.execute(
                    text(
                        "SELECT config_data FROM site_configs "
                        "WHERE site_id = :site_id AND config_type = 'ontology'"
                    ),
                    {"site_id": site_id_int},
                ).fetchone()

                prev_data = old_row[0] if old_row else None
                if prev_data and isinstance(prev_data, str):
                    prev_data = json.loads(prev_data)

                new_data = config.model_dump()
                diff = _compute_diff(prev_data, new_data)
                prev_json = json.dumps(prev_data) if prev_data else None

                conn.execute(
                    text(
                        "INSERT INTO config_audit_log "
                        "(site_id, config_type, action, changed_by, previous_data, new_data, diff_json) "
                        "VALUES (:site_id, 'ontology', :action, :changed_by, :prev, :new, :diff)"
                    ),
                    {
                        "site_id": site_id_int,
                        "action": "update" if old_row else "create",
                        "changed_by": changed_by,
                        "prev": prev_json,
                        "new": data_json,
                        "diff": json.dumps(diff),
                    },
                )

            conn.execute(
                text(
                    "INSERT INTO site_configs (site_id, config_type, config_data, version, updated_by) "
                    "VALUES (:site_id, 'ontology', :data, :version, :updated_by) "
                    "ON CONFLICT (site_id, config_type) "
                    "DO UPDATE SET config_data = :data, version = :version, "
                    "updated_by = :updated_by, updated_at = CURRENT_TIMESTAMP"
                ),
                {
                    "site_id": site_id_int,
                    "data": data_json,
                    "version": config.version,
                    "updated_by": changed_by,
                },
            )

        logger.info("Saved ontology config for site_id=%s", site_id)

    def exists(self, site_id: str = "default") -> bool:
        site_id_int = self._resolve_site_id(site_id)
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT 1 FROM site_configs "
                    "WHERE site_id = :site_id AND config_type = 'ontology'"
                ),
                {"site_id": site_id_int},
            ).fetchone()
        return row is not None

    def _resolve_site_id(self, site_id: str) -> int:
        if site_id == "default":
            return 1
        return int(site_id)
