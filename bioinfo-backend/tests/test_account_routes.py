"""Tests for DELETE /auth/history and DELETE /auth/account (database mocked)."""
import os
import sys
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.api.main import app
from src.api.routes import auth as auth_routes
from src.services.auth_service import create_access_token


class FakeSession:
    """Records executed statements; reports `rowcount` for each."""

    def __init__(self, rowcount=3):
        self.statements = []
        self.rowcount = rowcount

    async def execute(self, stmt):
        self.statements.append(stmt)
        return SimpleNamespace(rowcount=self.rowcount)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def user_id():
    return uuid.uuid4()


@pytest.fixture
def auth_headers(user_id):
    token = create_access_token(user_id=user_id, email="t@example.com", name="T")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def fake_db(monkeypatch):
    session = FakeSession()

    @asynccontextmanager
    async def fake_get_session():
        yield session

    monkeypatch.setattr(auth_routes, "is_db_available", lambda: True)
    monkeypatch.setattr(auth_routes, "get_session", fake_get_session)
    return session


def _table_and_params(stmt):
    compiled = stmt.compile()
    return stmt.table.name, list(compiled.params.values())


@pytest.mark.parametrize("path", ["/api/v1/auth/history", "/api/v1/auth/account"])
def test_requires_auth(client, path):
    assert client.delete(path).status_code == 401


def test_clear_history_deletes_only_own_queries(client, auth_headers, user_id, fake_db):
    r = client.delete("/api/v1/auth/history", headers=auth_headers)

    assert r.status_code == 200
    assert r.json() == {"status": "cleared", "deleted_queries": 3}
    assert [_table_and_params(s) for s in fake_db.statements] == [("queries", [user_id])]


def test_delete_account_removes_queries_then_user(client, auth_headers, user_id, fake_db):
    r = client.delete("/api/v1/auth/account", headers=auth_headers)

    assert r.status_code == 200
    assert r.json() == {"status": "deleted", "deleted_queries": 3}
    assert [_table_and_params(s) for s in fake_db.statements] == [
        ("queries", [user_id]),
        ("users", [user_id]),
    ]


@pytest.mark.parametrize("path,status", [
    ("/api/v1/auth/history", "cleared"),
    ("/api/v1/auth/account", "deleted"),
])
def test_without_database_is_a_noop(client, auth_headers, monkeypatch, path, status):
    monkeypatch.setattr(auth_routes, "is_db_available", lambda: False)
    r = client.delete(path, headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == {"status": status, "deleted_queries": 0}
