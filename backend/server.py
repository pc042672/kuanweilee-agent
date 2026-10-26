import logging
import os
import time
import uvicorn
from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import backend.settings as settings
from backend.logging_config import setup_logging

setup_logging()

# ADK Cloud Trace: set OpenTelemetry env vars before ADK imports
if settings.ENABLE_CLOUD_TRACE:
    os.environ.setdefault("ENABLE_TRACING", "true")
    os.environ.setdefault("TRACE_EXPORTER", "cloud_trace")

logger = logging.getLogger("ai_cdp.server")


def get_cors_origins() -> List[str]:
    """Get CORS origins from environment or use defaults for development."""
    cors_env = settings.CORS_ORIGINS.strip()
    if cors_env:
        return [origin.strip() for origin in cors_env.split(",") if origin.strip()]
    return ["http://localhost:4200", "http://127.0.0.1:4200"]


from google.adk.runners import Runner
from google.adk.apps import App
from google.adk.sessions import InMemorySessionService
from google.genai import types
from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint

from backend.config import get_config_manager
from backend.context import set_request_context
from backend.auth import (
    UserContext, get_current_user, verify_google_id_token,
    create_session_jwt, verify_session_jwt,
    DEV_USER_EMAIL, _API_KEY, _DEV_CTX,
)

print(f"APP_ENV={settings.APP_ENV} | auth_required={settings.AUTH_REQUIRED} | rate_limit={settings.RATE_LIMIT_ENABLED} | model_guard={settings.ENABLE_MODEL_GUARD}")

config = get_config_manager()
try:
    ontology = config.load_ontology()
    print(f"Configuration loaded: ontology v{ontology.version}, {len(ontology.nodes)} nodes")
except FileNotFoundError as e:
    print(f"WARNING: Ontology config not found - {e}")
    print("  Server will start but agents will not have business context.")
except Exception as e:
    print(f"ERROR: Configuration validation failed - {e}")
    raise

from backend.revive_agent.agent import revive_orchestrator
from backend.revive_agent.plugins import LoggingPlugin, ServiceGatingPlugin, SQLSafetyPlugin

_plugins = [LoggingPlugin(), SQLSafetyPlugin(), ServiceGatingPlugin()]
if settings.ENABLE_MODEL_GUARD:
    from backend.revive_agent.plugins import ModelGuardPlugin
    _plugins.append(ModelGuardPlugin())
    logger.info("ModelGuardPlugin enabled (ENABLE_MODEL_GUARD=true)")

revive_app = App(
    name="revive_ai",
    root_agent=revive_orchestrator,
    plugins=_plugins,
)


def _create_session_service():
    """Create session service from DATABASE_URL (production) or InMemory (dev)."""
    if settings.DATABASE_URL:
        from google.adk.sessions import DatabaseSessionService
        # ADK requires async driver — convert psycopg2 URL to asyncpg
        async_url = settings.DATABASE_URL.replace(
            "postgresql+psycopg2://", "postgresql+asyncpg://"
        ).replace("postgresql://", "postgresql+asyncpg://")
        logger.info("Using DatabaseSessionService")
        return DatabaseSessionService(db_url=async_url)
    logger.info("Using InMemorySessionService")
    return InMemorySessionService()


def _create_memory_service():
    """Long-term memory: Postgres-backed in production, in-memory in dev."""
    if settings.DATABASE_URL:
        from backend.db import get_engine
        from backend.memory import PostgresMemoryService
        logger.info("Using PostgresMemoryService")
        return PostgresMemoryService(get_engine())
    from google.adk.memory import InMemoryMemoryService
    logger.info("Using InMemoryMemoryService")
    return InMemoryMemoryService()


session_service = _create_session_service()
memory_service = _create_memory_service()
PERSISTENT_SESSIONS = bool(settings.DATABASE_URL)

_SKIP_AUTH_PATHS = frozenset({
    "/api/auth/login", "/api/auth/register", "/api/auth/config",
    "/health", "/docs", "/openapi.json",
})

_GUEST_CTX = UserContext(user_id=0, email="anonymous", name="", site_id=1, role="guest")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.orchestrator = revive_orchestrator
    app.state.revive_app = revive_app
    print("Server started, AG-UI endpoint available at /ag-ui")
    yield
    print("Server shutting down...")


app = FastAPI(lifespan=lifespan)

cors_origins = get_cors_origins()
if not settings.DEV_MODE and not settings.CORS_ORIGINS.strip():
    logger.warning("CORS_ORIGINS not set in production — using localhost defaults. Set CORS_ORIGINS env var.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Requested-With"],
)


# Simple in-memory rate limiter (per-IP, 120 requests/minute)
_rate_buckets: dict = {}  # ip -> (count, window_start)
_RATE_LIMIT = 120
_RATE_WINDOW = 60  # seconds


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Simple per-IP rate limiting. In production, prefer Cloud Armor rules."""
    if not settings.RATE_LIMIT_ENABLED:
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    count, window_start = _rate_buckets.get(client_ip, (0, now))

    if now - window_start > _RATE_WINDOW:
        count, window_start = 0, now

    count += 1
    _rate_buckets[client_ip] = (count, window_start)

    # Evict stale entries to prevent unbounded growth
    if len(_rate_buckets) > 10_000:
        cutoff = now - 2 * _RATE_WINDOW
        stale = [ip for ip, (_, ws) in _rate_buckets.items() if ws < cutoff]
        for ip in stale:
            del _rate_buckets[ip]

    if count > _RATE_LIMIT:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again later."},
        )
    return await call_next(request)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """Set request-scoped UserContext for all requests."""
    if request.url.path in _SKIP_AUTH_PATHS:
        return await call_next(request)

    if not settings.AUTH_REQUIRED:
        set_request_context(_DEV_CTX)
        return await call_next(request)

    try:
        ctx = _resolve_context(request)
    except HTTPException as exc:
        from starlette.responses import JSONResponse
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    set_request_context(ctx)
    return await call_next(request)


def _resolve_context(request: Request) -> UserContext:
    """Extract auth context from request headers without FastAPI DI.

    When a Bearer token is present, it MUST be valid — invalid tokens
    raise HTTPException(401) rather than falling through to dev mode.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        payload = verify_session_jwt(auth_header[7:])
        return UserContext(
            user_id=payload["user_id"],
            email=payload["email"],
            name=payload.get("name", ""),
            site_id=payload["site_id"],
            role=payload["role"],
        )

    api_key = request.headers.get("X-API-Key")
    if _API_KEY and api_key == _API_KEY:
        return UserContext(
            user_id=1, email="api-key-user@legacy", name="API Key User",
            site_id=1, role="admin",
        )

    return _GUEST_CTX


def _agui_user_id(_input) -> str:
    """Resolve the AG-UI session owner from the authenticated request context.

    Keeps /ag-ui sessions under the same user key as /api/chat/stream and the
    chat-history API (user email). Falls back to a thread-scoped pseudo-user
    when unauthenticated (guest)."""
    from backend.context import get_request_context_or_none
    ctx = get_request_context_or_none()
    if ctx and ctx.email and ctx.email != "anonymous":
        return ctx.email
    return f"thread_user_{_input.thread_id}"


adk_agent = ADKAgent.from_app(
    app=revive_app,
    session_service=session_service,
    memory_service=memory_service,
    user_id_extractor=_agui_user_id,
    # AG-UI thread id == ADK session id, so the chat-history API and the
    # frontend thread list address the same sessions.
    use_thread_id_as_session_id=True,
    # Memory ingestion happens per-run via the orchestrator's
    # after_agent_callback; the cleanup-time ingestion would be redundant.
    save_session_to_memory_on_cleanup=False,
    emit_messages_snapshot=False,
)
add_adk_fastapi_endpoint(app, adk_agent, path="/ag-ui")


class LoginRequest(BaseModel):
    id_token: str


class LoginResponse(BaseModel):
    token: str
    user: dict


@app.get("/api/auth/config")
async def auth_config():
    """Public auth config for the frontend (Google OAuth client ID)."""
    return {"google_client_id": settings.GOOGLE_CLIENT_ID}


@app.post("/api/auth/login", response_model=LoginResponse)
async def auth_login(request: LoginRequest):
    """Verify Google ID token, upsert user in DB, return session JWT."""
    google_info = verify_google_id_token(request.id_token)

    from backend.db import get_engine
    from sqlalchemy import text

    engine = get_engine()
    if engine:
        with engine.begin() as conn:
            # Upsert user: match by google_id, or by email (for init_db placeholder)
            row = conn.execute(text(
                "SELECT id FROM users WHERE google_id = :gid"
            ), {"gid": google_info["google_id"]}).fetchone()

            if row:
                user_id = row[0]
                conn.execute(text(
                    "UPDATE users SET email = :email, name = :name, avatar_url = :avatar "
                    "WHERE id = :uid"
                ), {
                    "email": google_info["email"],
                    "name": google_info["name"],
                    "avatar": google_info["avatar_url"],
                    "uid": user_id,
                })
            else:
                # Check if email exists (init_db placeholder with google_id='init:...')
                row = conn.execute(text(
                    "SELECT id FROM users WHERE email = :email"
                ), {"email": google_info["email"]}).fetchone()

                if row:
                    user_id = row[0]
                    conn.execute(text(
                        "UPDATE users SET google_id = :gid, name = :name, avatar_url = :avatar "
                        "WHERE id = :uid"
                    ), {
                        "gid": google_info["google_id"],
                        "name": google_info["name"],
                        "avatar": google_info["avatar_url"],
                        "uid": user_id,
                    })
                else:
                    user_id = conn.execute(text(
                        "INSERT INTO users (google_id, email, name, avatar_url) "
                        "VALUES (:gid, :email, :name, :avatar) RETURNING id"
                    ), {
                        "gid": google_info["google_id"],
                        "email": google_info["email"],
                        "name": google_info["name"],
                        "avatar": google_info["avatar_url"],
                    }).scalar()

                    # Auto-join default site as member
                    conn.execute(text(
                        "INSERT INTO site_members (site_id, user_id, role) "
                        "VALUES (1, :uid, 'member') "
                        "ON CONFLICT (site_id, user_id) DO NOTHING"
                    ), {"uid": user_id})

            # Get site membership
            membership = conn.execute(text(
                "SELECT site_id, role FROM site_members WHERE user_id = :uid LIMIT 1"
            ), {"uid": user_id}).fetchone()

            site_id = membership[0] if membership else 1
            role = membership[1] if membership else "member"
    else:
        user_id = 1
        site_id = 1
        role = "admin"

    token = create_session_jwt({
        "user_id": user_id,
        "email": google_info["email"],
        "name": google_info["name"],
        "site_id": site_id,
        "role": role,
        "google_id": google_info["google_id"],
    })

    return LoginResponse(
        token=token,
        user={
            "email": google_info["email"],
            "name": google_info["name"],
            "avatar_url": google_info["avatar_url"],
        },
    )


@app.get("/api/auth/me")
async def auth_me(user: UserContext = Depends(get_current_user)):
    """Return current user info from session JWT."""
    return {
        "user_id": user.user_id,
        "email": user.email,
        "name": user.name,
        "site_id": user.site_id,
        "role": user.role,
    }


class ChatRequest(BaseModel):
    session_id: str
    message: str
    user_id: str = "default_user"


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """Streams ADK Events to the frontend."""
    revive_orchestrator = app.state.orchestrator

    if not await session_service.get_session(app_name="revive_ai", user_id=request.user_id, session_id=request.session_id):
        await session_service.create_session(app_name="revive_ai", user_id=request.user_id, session_id=request.session_id)

    runner = Runner(
        app=app.state.revive_app,
        session_service=session_service,
        memory_service=memory_service,
    )

    user_content = types.Content(role="user", parts=[types.Part(text=request.message)])

    async def event_generator():
        async for event in runner.run_async(
            session_id=request.session_id,
            user_id=request.user_id,
            new_message=user_content
        ):
            yield event.model_dump_json() + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@app.get("/health")
async def health():
    return {"status": "ok", "persistent_sessions": PERSISTENT_SESSIONS}


from backend.routers.ontology import router as ontology_router
from backend.routers.brand import router as brand_router
from backend.routers.config_reload import router as config_reload_router
from backend.routers.chat_history import router as chat_history_router
from backend.routers.integrations import router as integrations_router
from backend.persona.router import router as persona_router
from backend.routers.integrations import router as integrations_router

app.include_router(ontology_router)
app.include_router(brand_router)
app.include_router(config_reload_router)
app.include_router(chat_history_router)
app.include_router(integrations_router)
app.include_router(persona_router)
app.include_router(integrations_router)


# Serve Angular SPA from static/ in production (built by Dockerfile)
_static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.isdir(_static_dir):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
