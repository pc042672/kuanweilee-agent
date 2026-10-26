"""Chat-history API — thin wrappers over the ADK session service.

Sessions and events are owned by ADK's DatabaseSessionService (or InMemory in
dev); this router never touches ADK's tables directly. Sessions are scoped to
the authenticated user — the caller can only list/read/delete their own.
"""

from fastapi import APIRouter, Depends, HTTPException

from backend.auth import UserContext, get_current_user

APP_NAME = "revive_ai"

router = APIRouter(prefix="/api/chat", tags=["chat-history"])


def _session_service():
    from backend.server import session_service
    return session_service


def _memory_service():
    from backend.server import memory_service
    return memory_service


@router.get("/capabilities")
async def capabilities():
    """Feature flags the frontend adapts to (no auth — non-sensitive)."""
    from backend.server import PERSISTENT_SESSIONS
    return {"persistent_sessions": PERSISTENT_SESSIONS}


@router.get("/sessions")
async def list_sessions(user: UserContext = Depends(get_current_user)):
    """List the caller's chat sessions, newest first."""
    response = await _session_service().list_sessions(
        app_name=APP_NAME, user_id=user.email
    )
    sessions = sorted(
        response.sessions, key=lambda s: s.last_update_time or 0, reverse=True
    )
    return {
        "sessions": [
            {"id": s.id, "last_update_time": s.last_update_time}
            for s in sessions
        ]
    }


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: str, user: UserContext = Depends(get_current_user)
):
    """Return the user/assistant text messages of one session."""
    session = await _session_service().get_session(
        app_name=APP_NAME, user_id=user.email, session_id=session_id
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = []
    for event in session.events or []:
        if not event.content or not event.content.parts:
            continue
        text = " ".join(p.text for p in event.content.parts if p.text)
        if not text.strip():
            continue  # tool calls / non-text events
        messages.append({
            "role": "user" if event.author == "user" else "assistant",
            "author": event.author,
            "text": text,
            "timestamp": event.timestamp,
        })
    return {"id": session.id, "messages": messages}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str, user: UserContext = Depends(get_current_user)
):
    """Delete one of the caller's sessions (and its distilled memories)."""
    session = await _session_service().get_session(
        app_name=APP_NAME, user_id=user.email, session_id=session_id
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    await _session_service().delete_session(
        app_name=APP_NAME, user_id=user.email, session_id=session_id
    )
    memory = _memory_service()
    if hasattr(memory, "delete_session_memories"):
        memory.delete_session_memories(
            app_name=APP_NAME, user_id=user.email, session_id=session_id
        )
    return {"deleted": session_id}
