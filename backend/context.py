"""
Request-scoped context via contextvars.

Stores the authenticated UserContext for the current request. Set once
in auth middleware, read by tools via get_request_context().
"""

import contextvars
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from auth import UserContext

_request_ctx: contextvars.ContextVar["UserContext | None"] = (
    contextvars.ContextVar("request_ctx", default=None)
)


def set_request_context(ctx: "UserContext") -> contextvars.Token:
    return _request_ctx.set(ctx)


def reset_request_context(token: contextvars.Token) -> None:
    """Reset context to its previous value. Used in tests for isolation."""
    _request_ctx.reset(token)


def get_request_context() -> "UserContext":
    ctx = _request_ctx.get()
    if ctx is None:
        raise RuntimeError("Request context not initialized — missing auth middleware?")
    return ctx


def get_request_context_or_none() -> "Optional[UserContext]":
    return _request_ctx.get()
