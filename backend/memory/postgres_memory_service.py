"""PostgreSQL-backed long-term memory for ADK agents.

Implements google.adk.memory.BaseMemoryService against the `memories` table
(migration 007). Modeled on ADK's InMemoryMemoryService, with two deliberate
differences for compliance (financial-industry product):

- Persistence gate: only DISTILLED session facts are stored — campaign
  decisions (`campaign_summary`), analysis/segment definitions
  (`execution_plan`), and explicit user preference statements. Full
  conversation transcripts are never persisted.
- Site scoping + delete path: rows carry site_id; `delete_memories()` makes
  users forgettable.

Search is lexical (PostgreSQL full-text, 'simple' config — tokenizes mixed
zh/en). An embedding backend can replace `search_memory` behind the same
BaseMemoryService interface later.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Optional

from google.adk.memory import _utils
from google.adk.memory.base_memory_service import (
    BaseMemoryService,
    SearchMemoryResponse,
)
from google.adk.memory.memory_entry import MemoryEntry
from google.genai import types
from sqlalchemy import text
from sqlalchemy.engine import Engine

if TYPE_CHECKING:
    from google.adk.sessions.session import Session

logger = logging.getLogger("ai_cdp.memory")

_SEARCH_LIMIT = 10

# Session-state keys whose values are worth remembering, with the memory kind.
_STATE_FACTS = [
    ("campaign_summary", "campaign_summary"),
    ("execution_plan", "analysis"),
]

# A user message is stored as a preference only when it states a durable
# instruction (multi-language heuristics; tune as the product grows).
_PREFERENCE_PATTERNS = re.compile(
    r"always|never|prefer|from now on|do not|don't|每次|以後|以后|永遠|永远|不要|偏好",
    re.IGNORECASE,
)


def _content_text(content: Optional[types.Content]) -> str:
    if not content or not content.parts:
        return ""
    return " ".join(p.text for p in content.parts if p.text)


class PostgresMemoryService(BaseMemoryService):
    """BaseMemoryService backed by the `memories` table."""

    def __init__(self, engine: Engine):
        self._engine = engine

    # ── ingest ─────────────────────────────────────────────────────

    async def add_session_to_memory(self, session: Session):
        """Distill a session into memory rows (replaces the session's prior rows)."""
        facts = self._distill(session)

        with self._engine.begin() as conn:
            # Site scope from the user's membership (user_id is the email for
            # authenticated sessions; guests resolve to NULL).
            site_id = conn.execute(
                text(
                    "SELECT m.site_id FROM site_members m "
                    "JOIN users u ON u.id = m.user_id "
                    "WHERE u.email = :email ORDER BY m.site_id LIMIT 1"
                ),
                {"email": session.user_id},
            ).scalar()
            conn.execute(
                text(
                    "DELETE FROM memories WHERE app_name = :app AND user_id = :uid "
                    "AND session_id = :sid"
                ),
                {"app": session.app_name, "uid": session.user_id, "sid": session.id},
            )
            for kind, author, timestamp, content in facts:
                body = _content_text(content)
                if not body.strip():
                    continue
                conn.execute(
                    text(
                        "INSERT INTO memories (app_name, user_id, session_id, site_id, "
                        'kind, author, "timestamp", content, text) '
                        "VALUES (:app, :uid, :sid, :site, :kind, :author, "
                        "to_timestamp(:ts), :content, :text)"
                    ),
                    {
                        "app": session.app_name,
                        "uid": session.user_id,
                        "sid": session.id,
                        "site": site_id,
                        "kind": kind,
                        "author": author,
                        "ts": timestamp,
                        "content": json.dumps(content.model_dump(mode="json")),
                        "text": body[:8000],
                    },
                )
        logger.info(
            "memory: stored %d fact(s) for session %s/%s",
            len(facts), session.user_id, session.id,
        )

    def _distill(self, session: Session):
        """Extract (kind, author, timestamp, Content) facts. The gate: state facts
        + user preference statements only — never the raw transcript."""
        facts = []
        now = session.last_update_time or 0.0

        state = session.state or {}
        for state_key, kind in _STATE_FACTS:
            value = state.get(state_key)
            if not value:
                continue
            body = value if isinstance(value, str) else json.dumps(
                value, ensure_ascii=False, default=str
            )
            facts.append((
                kind,
                "model",
                now,
                types.Content(role="model", parts=[types.Part(text=body)]),
            ))

        for event in session.events or []:
            if event.author != "user" or not event.content:
                continue
            body = _content_text(event.content)
            if body and _PREFERENCE_PATTERNS.search(body):
                facts.append((
                    "preference",
                    "user",
                    event.timestamp or now,
                    types.Content(role="user", parts=[types.Part(text=body)]),
                ))

        return facts

    # ── recall ─────────────────────────────────────────────────────

    async def search_memory(
        self, *, app_name: str, user_id: str, query: str
    ) -> SearchMemoryResponse:
        response = SearchMemoryResponse()
        if not query.strip():
            return response

        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT content, author, EXTRACT(EPOCH FROM \"timestamp\") "
                    "FROM memories "
                    "WHERE app_name = :app AND user_id = :uid "
                    "AND tsv @@ plainto_tsquery('simple', :q) "
                    "ORDER BY ts_rank(tsv, plainto_tsquery('simple', :q)) DESC "
                    "LIMIT :lim"
                ),
                {"app": app_name, "uid": user_id, "q": query, "lim": _SEARCH_LIMIT},
            ).fetchall()

        for content_json, author, epoch in rows:
            data = content_json if isinstance(content_json, dict) else json.loads(content_json)
            response.memories.append(
                MemoryEntry(
                    content=types.Content(**data),
                    author=author,
                    timestamp=_utils.format_timestamp(float(epoch)),
                )
            )
        return response

    # ── compliance ─────────────────────────────────────────────────

    def delete_memories(self, user_id: str, app_name: Optional[str] = None) -> int:
        """Forget a user. Returns deleted row count."""
        clause = "user_id = :uid" + (" AND app_name = :app" if app_name else "")
        with self._engine.begin() as conn:
            result = conn.execute(
                text(f"DELETE FROM memories WHERE {clause}"),
                {"uid": user_id, "app": app_name},
            )
        return result.rowcount

    def delete_session_memories(
        self, *, app_name: str, user_id: str, session_id: str
    ) -> int:
        """Forget one session's distilled facts. Returns deleted row count."""
        with self._engine.begin() as conn:
            result = conn.execute(
                text(
                    "DELETE FROM memories WHERE app_name = :app AND user_id = :uid "
                    "AND session_id = :sid"
                ),
                {"app": app_name, "uid": user_id, "sid": session_id},
            )
        return result.rowcount
