"""Ontology repository abstraction layer.

Provides a Protocol for ontology storage operations and a JSON file
implementation. Database implementation in db_repository.py.
"""

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

from .schemas import UnifiedOntologyConfig


@runtime_checkable
class OntologyRepository(Protocol):
    """Abstract interface for ontology storage operations."""

    def load(self, site_id: str = "default") -> UnifiedOntologyConfig: ...
    def save(self, config: UnifiedOntologyConfig, site_id: str = "default") -> None: ...
    def exists(self, site_id: str = "default") -> bool: ...


class JsonOntologyRepository:
    """JSON file-based ontology repository.

    Stores config in config/ontology.json (default site) or
    config/sites/{site_id}/ontology.json (multi-site).
    """

    def __init__(self, config_dir: Path):
        self._config_dir = config_dir

    def _get_path(self, site_id: str) -> Path:
        if site_id == "default":
            return self._config_dir / "ontology.json"
        return self._config_dir / "sites" / site_id / "ontology.json"

    def load(self, site_id: str = "default") -> UnifiedOntologyConfig:
        path = self._get_path(site_id)
        if not path.exists():
            raise FileNotFoundError(f"Ontology config not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return UnifiedOntologyConfig(**data)

    def save(self, config: UnifiedOntologyConfig, site_id: str = "default") -> None:
        path = self._get_path(site_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config.model_dump(), f, indent=2, ensure_ascii=False)

    def exists(self, site_id: str = "default") -> bool:
        return self._get_path(site_id).exists()
