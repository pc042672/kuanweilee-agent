"""Source: a per-site database connection (JDBC-like), readonly-enforced."""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote_plus

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine

from dbtoolbox.dialects import DialectAdapter, get_dialect

logger = logging.getLogger("ai_cdp.dbtoolbox.sources")

# connection_config keys holding secrets: stored encrypted, stripped from API
# responses. Single source of truth for every consumer of data_sources rows.
SECRET_CONNECTION_KEYS = frozenset({"password", "readonly_password"})


@dataclass(frozen=True)
class SourceConfig:
    db_type: str
    host: str
    port: int
    dbname: str
    user: str  # readonly credentials only
    password: str = field(repr=False, default="")
    pool_size: int = 5
    max_overflow: int = 2
    pool_recycle: int = 3600
    statement_timeout_ms: int = 30_000

    @classmethod
    def from_env(cls, statement_timeout_ms: int = 30_000) -> "SourceConfig":
        """Env-var fallback (GP_*), matching the legacy GreenplumRunner defaults."""
        return cls(
            db_type="greenplum",
            host=os.getenv("GP_HOST", "localhost"),
            port=int(os.getenv("GP_PORT", "5432")),
            dbname=os.getenv("GP_DBNAME", "dev"),
            user=os.getenv("GP_READONLY_USER", os.getenv("GP_USER", "gpadmin")),
            password=os.getenv("GP_READONLY_PASSWORD", os.getenv("GP_PASSWORD", "pivotal")),
            pool_size=int(os.getenv("GP_POOL_MAX", "5")),
            statement_timeout_ms=statement_timeout_ms,
        )

    @classmethod
    def from_data_source_row(
        cls, row: dict, statement_timeout_ms: int = 30_000
    ) -> "SourceConfig":
        """Build from a data_sources table row ({db_type, connection_config}).

        Prefers readonly_user/readonly_password; falls back to user/password.
        """
        cfg = dict(row.get("connection_config") or {})
        return cls(
            db_type=row.get("db_type", "greenplum"),
            host=cfg.get("host", "localhost"),
            port=int(cfg.get("port", 5432)),
            dbname=cfg.get("dbname", ""),
            user=cfg.get("readonly_user") or cfg.get("user", ""),
            password=cfg.get("readonly_password") or cfg.get("password", ""),
            statement_timeout_ms=statement_timeout_ms,
        )


class Source:
    """Lazy SQLAlchemy engine wrapper with read-only session setup."""

    def __init__(self, config: SourceConfig):
        self.config = config
        self._engine: Optional[Engine] = None
        self._lock = threading.Lock()

    @property
    def dialect(self) -> DialectAdapter:
        return get_dialect(self.config.db_type)

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            with self._lock:
                if self._engine is None:
                    self._engine = self._create_engine()
        return self._engine

    def _create_engine(self) -> Engine:
        cfg = self.config
        # Credentials must be URL-escaped — passwords with @ : / % break the DSN.
        url = self.dialect.url_template.format(
            user=quote_plus(cfg.user),
            password=quote_plus(cfg.password),
            host=cfg.host,
            port=cfg.port,
            dbname=quote_plus(cfg.dbname),
        )
        engine = create_engine(
            url,
            pool_size=cfg.pool_size,
            max_overflow=cfg.max_overflow,
            pool_recycle=cfg.pool_recycle,
            pool_pre_ping=True,
        )
        setup = self.dialect.session_setup_statements(cfg.statement_timeout_ms)
        if setup:
            # "connect" fires once per real DBAPI connection (not per checkout),
            # so every pooled connection is read-only with a statement timeout.
            @event.listens_for(engine, "connect")
            def _setup_session(dbapi_conn, _record):
                cursor = dbapi_conn.cursor()
                try:
                    for stmt in setup:
                        cursor.execute(stmt)
                finally:
                    cursor.close()

        logger.info(
            "Source engine created: %s @ %s:%s/%s (readonly user=%s)",
            cfg.db_type, cfg.host, cfg.port, cfg.dbname, cfg.user,
        )
        return engine

    def test_connection(self) -> dict:
        """Connectivity check for the settings-page Test button."""
        start = time.monotonic()
        try:
            with self.engine.connect() as conn:
                version = conn.execute(text("SELECT version()")).scalar()
            return {
                "ok": True,
                "latency_ms": round((time.monotonic() - start) * 1000),
                "server_version": str(version)[:120] if version else None,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def dispose(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
