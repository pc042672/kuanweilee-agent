"""Tests for backend/context.py — contextvars request scope."""

import pytest

from auth import UserContext
from context import set_request_context, get_request_context, reset_request_context


class TestRequestContext:
    def test_set_and_get(self):
        ctx = UserContext(user_id=1, email="a@b.com", name="A", site_id=3, role="admin")
        token = set_request_context(ctx)
        try:
            result = get_request_context()
            assert result.site_id == 3
            assert result.email == "a@b.com"
        finally:
            reset_request_context(token)

    def test_raises_when_not_set(self):
        with pytest.raises(RuntimeError, match="Request context not initialized"):
            get_request_context()

    def test_reset_clears_context(self):
        ctx = UserContext(user_id=1, email="a@b.com", name="A", site_id=1, role="admin")
        token = set_request_context(ctx)
        reset_request_context(token)
        with pytest.raises(RuntimeError):
            get_request_context()

    def test_nested_contexts(self):
        ctx1 = UserContext(user_id=1, email="a@b.com", name="A", site_id=1, role="admin")
        ctx2 = UserContext(user_id=2, email="b@c.com", name="B", site_id=2, role="member")

        token1 = set_request_context(ctx1)
        assert get_request_context().site_id == 1

        token2 = set_request_context(ctx2)
        assert get_request_context().site_id == 2

        reset_request_context(token2)
        assert get_request_context().site_id == 1

        reset_request_context(token1)
