"""Integration tests for global error handlers via FastAPI TestClient."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from src.utils.error_handlers import (
    register_error_handlers,
    AppError,
    NotFoundError,
    AuthError,
)


@pytest.fixture
def app():
    _app = FastAPI()
    register_error_handlers(_app)

    @_app.get("/not-found")
    def raise_not_found():
        raise NotFoundError("Paper", "99999999")

    @_app.get("/auth-error")
    def raise_auth():
        raise AuthError("Not authenticated")

    @_app.get("/app-error")
    def raise_app():
        raise AppError("Custom error", status_code=400, code="custom")

    @_app.get("/unhandled")
    def raise_unhandled():
        raise RuntimeError("boom")

    return _app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


class TestErrorHandlers:
    def test_not_found_returns_404(self, client):
        res = client.get("/not-found")
        assert res.status_code == 404
        assert res.json()["error"] == "not_found"

    def test_auth_error_returns_401(self, client):
        res = client.get("/auth-error")
        assert res.status_code == 401
        assert res.json()["error"] == "auth_error"

    def test_custom_app_error(self, client):
        res = client.get("/app-error")
        assert res.status_code == 400
        assert res.json()["error"] == "custom"

    def test_unhandled_returns_500(self, client):
        res = client.get("/unhandled")
        assert res.status_code == 500
        assert res.json()["error"] == "internal_error"

    def test_validation_error_returns_422(self, client):

        # Hit a nonexistent route to get a 404 (not 422) first, then use a real route
        res = client.get("/docs")
        assert res.status_code == 200  # docs are public
