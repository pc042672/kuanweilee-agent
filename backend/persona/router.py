"""
FastAPI router for persona classification endpoints.
"""

import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from backend.persona.schemas import (
    PersonaClassifyRequest, PersonaBatchClassifyRequest, PersonaAnalyzeRequest
)
from backend.auth import UserContext, get_current_user
from backend.persona.search import fast_persona_classify
from backend.services import credentials as credentials_service

router = APIRouter(prefix="/api/persona", tags=["persona"], dependencies=[Depends(get_current_user)])


def _require_vertex(site_id: int) -> dict:
    """Resolved vertex_ai credentials for the site, or HTTP 409 when unconfigured."""
    return credentials_service.require_credentials(site_id, "vertex_ai")


@router.post("/classify")
async def classify_persona(
    request: PersonaClassifyRequest, user: UserContext = Depends(get_current_user)
):
    """
    Fast mode: classify content against Jungian persona taxonomy via vector search.
    Returns archetypes sorted by score with match details.
    """
    creds = _require_vertex(user.site_id)
    try:
        result = fast_persona_classify(
            content=request.content,
            top_k=request.top_k,
            category_filter=request.category_filter,
            project_id=creds.get("project_id"),
            location=creds.get("location"),
        )
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Persona classification failed: {str(e)}")


@router.post("/classify/batch")
async def classify_persona_batch(
    request: PersonaBatchClassifyRequest, user: UserContext = Depends(get_current_user)
):
    """
    Batch fast mode: classify multiple pieces of content.
    """
    creds = _require_vertex(user.site_id)
    try:
        results = []
        for content in request.contents:
            result = fast_persona_classify(
                content=content,
                top_k=request.top_k,
                category_filter=request.category_filter,
                project_id=creds.get("project_id"),
                location=creds.get("location"),
            )
            results.append(result.model_dump())
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch classification failed: {str(e)}")


@router.post("/analyze")
async def analyze_persona(
    request: PersonaAnalyzeRequest, user: UserContext = Depends(get_current_user)
):
    """
    Advanced mode: agentic RAG persona analysis with LLM reasoning.
    Streams ADK events via SSE.
    """
    _require_vertex(user.site_id)
    from backend.persona.agent import persona_agent

    # Per-request session service — persona sessions are single-turn and not reused
    session_service = InMemorySessionService()

    runner = Runner(
        agent=persona_agent,
        app_name="persona_analyzer",
        session_service=session_service,
    )

    session = await session_service.create_session(
        app_name="persona_analyzer",
        user_id="persona_user",
    )

    user_content = types.Content(
        role="user",
        parts=[types.Part(text=request.content)],
    )

    async def event_stream():
        async for event in runner.run_async(
            user_id="persona_user",
            session_id=session.id,
            new_message=user_content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        yield f"data: {json.dumps({'type': 'text', 'content': part.text})}\n\n"
                    elif part.function_call:
                        yield f"data: {json.dumps({'type': 'tool_call', 'name': part.function_call.name, 'args': part.function_call.args})}\n\n"
                    elif part.function_response:
                        yield f"data: {json.dumps({'type': 'tool_result', 'name': part.function_response.name})}\n\n"

            if event.actions and event.actions.escalate:
                break

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/taxonomy/reload")
async def reload_taxonomy(user: UserContext = Depends(get_current_user)):
    """Re-ingest taxonomy CSV into Vector Search 2.0 collection."""
    creds = _require_vertex(user.site_id)
    from backend.persona.ingestion import ingest
    try:
        total = ingest(
            project_id=creds.get("project_id"), location=creds.get("location")
        )
        return {"status": "success", "records_ingested": total}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Taxonomy reload failed: {str(e)}")
