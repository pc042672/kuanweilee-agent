"""Shared test fixtures."""

import os
import sys
import pytest

# Ensure backend (bare-path convention) and deploy scripts are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "deploy"))

# Set dev mode for all tests
os.environ.setdefault("DEV_USER_EMAIL", "test@dev.com")
os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")


@pytest.fixture
def jwt_payload():
    return {
        "user_id": 42,
        "email": "alice@example.com",
        "name": "Alice",
        "site_id": 5,
        "role": "admin",
    }
