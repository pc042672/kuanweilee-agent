"""
Central database engine.

Production: Set DATABASE_URL to PostgreSQL connection string.
Development: Leave unset — falls back to JSON files + InMemorySessionService.
"""

import logging
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

import settings

logger = logging.getLogger(__name__)

_engine: Optional[Engine] = None


def get_engine() -> Optional[Engine]:
    """Get the default database engine. Returns None if DATABASE_URL is not set."""
    global _engine
    if _engine is not None:
        return _engine

    if not settings.DATABASE_URL:
        return None

    _engine = create_engine(settings.DATABASE_URL, pool_size=5, pool_recycle=3600)
    logger.info("Database engine created")
    return _engine
