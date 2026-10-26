"""Rule/score engine config repository — behavior-layer storage.

Mirrors repository.py / db_repository.py but for RulesConfig. JSON stores
config/rules.json (or config/sites/{site_id}/rules.json); the database stores a
site_configs row with config_type='rules'.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .rules_schema import RulesConfig

logger = logging.getLogger(__name__)


@runtime_checkable
class RulesRepository(Protocol):
    """Abstract interface for rule/score engine config storage."""

    def load(self, site_id: str = "default") -> RulesConfig: ...
    def save(self, config: RulesConfig, site_id: str = "default") -> None: ...
    def exists(self, site_id: str = "default") -> bool: ...


class JsonRulesRepository:
    """JSON file-based rules repository (config/rules.json)."""

    def __init__(self, config_dir: Path):
        self._config_dir = config_dir

    def _get_path(self, site_id: str) -> Path:
        if site_id == "default":
            return self._config_dir / "rules.json"
        return self._config_dir / "sites" / site_id / "rules.json"

    def load(self, site_id: str = "default") -> RulesConfig:
        path = self._get_path(site_id)
        if not path.exists():
            raise FileNotFoundError(f"Rules config not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return RulesConfig(**data)

    def save(self, config: RulesConfig, site_id: str = "default") -> None:
        path = self._get_path(site_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config.model_dump(), f, indent=2, ensure_ascii=False)

    def exists(self, site_id: str = "default") -> bool:
        return self._get_path(site_id).exists()


class DbRulesRepository:
    """PostgreSQL implementation — site_configs row with config_type='rules'."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def load(self, site_id: str = "default") -> RulesConfig:
        site_id_int = self._resolve_site_id(site_id)
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT config_data FROM site_configs "
                    "WHERE site_id = :site_id AND config_type = 'rules'"
                ),
                {"site_id": site_id_int},
            ).fetchone()
        if row is None:
            raise FileNotFoundError(f"Rules config not found for site_id={site_id}")
        data = row[0]
        if isinstance(data, str):
            data = json.loads(data)
        return RulesConfig(**data)

    def save(self, config: RulesConfig, site_id: str = "default") -> None:
        site_id_int = self._resolve_site_id(site_id)
        data_json = json.dumps(config.model_dump())
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO site_configs (site_id, config_type, config_data, version, updated_by) "
                    "VALUES (:site_id, 'rules', :data, :version, NULL) "
                    "ON CONFLICT (site_id, config_type) "
                    "DO UPDATE SET config_data = :data, version = :version, "
                    "updated_at = CURRENT_TIMESTAMP"
                ),
                {"site_id": site_id_int, "data": data_json, "version": config.version},
            )
        logger.info("Saved rules config for site_id=%s", site_id)

    def exists(self, site_id: str = "default") -> bool:
        site_id_int = self._resolve_site_id(site_id)
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT 1 FROM site_configs "
                    "WHERE site_id = :site_id AND config_type = 'rules'"
                ),
                {"site_id": site_id_int},
            ).fetchone()
        return row is not None

    def _resolve_site_id(self, site_id: str) -> int:
        if site_id == "default":
            return 1
        return int(site_id)
