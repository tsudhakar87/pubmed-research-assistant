"""A failed history save must not cost the user their results."""
import os
import sys
import uuid
from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.api.main import app
from src.api.routes import query as query_routes
from src.api.routes import websocket as ws_routes
from src.models.response_models import PaperResult, QueryResponse
from src.services import query_store
from src.services.auth_service import create_access_token
from src.services.query_store import mark_unsaved, save_query


def _response():
    return QueryResponse(
        query_id="q_test", original_query="metformin microbiome", processing_time=5,
        literature_results=[PaperResult(title="P", authors=[], pmid="1", source="pubmed")],
        total_results=1, metadata={"sort_by": "relevance"},
    )


class FailingSession:
    def add(self, obj):
        pass

    async def flush(self):
        raise RuntimeError('column "source" of relation "query_papers" does not exist')


@pytest.fixture
def bq_calls(monkeypatch):
    calls = []

    async def fake_insert(**kw):
        calls.append(kw["query_id"])
    monkeypatch.setattr(query_store, "insert_query_event", fake_insert)
    return calls


@pytest.fixture
def failing_db(monkeypatch):
    @asynccontextmanager
    async def session():
        yield FailingSession()
    monkeypatch.setattr(query_store, "is_db_available", lambda: True)
    monkeypatch.setattr(query_store, "get_session", session)


class TestSaveQuery:
    async def test_db_failure_returns_false_and_still_logs_event(self, failing_db, bq_calls):
        assert await save_query("q1", uuid.uuid4(), _response()) is False
        assert bq_calls == ["q1"]

    async def test_no_db_counts_as_saved(self, monkeypatch, bq_calls):
        monkeypatch.setattr(query_store, "is_db_available", lambda: False)
        assert await save_query("q2", None, _response()) is True
        assert bq_calls == ["q2"]

    async def test_success(self, monkeypatch, bq_calls):
        added = []

        class OkSession:
            def add(self, obj):
                added.append(type(obj).__name__)

            async def flush(self):
                pass

        @asynccontextmanager
        async def session():
            yield OkSession()
        monkeypatch.setattr(query_store, "is_db_available", lambda: True)
        monkeypatch.setattr(query_store, "get_session", session)
        assert await save_query("q3", None, _response()) is True
        assert added == ["Query", "QueryPaper"]


def test_mark_unsaved_keeps_existing_metadata():
    r = mark_unsaved(_response())
    assert r.metadata == {"sort_by": "relevance", "history_saved": False}


class FakeAgent:
    async def process_query(self, query_request, query_id, include_ai_summary=True, progress_callback=None):
        return _response().model_copy(update={"query_id": query_id})


@pytest.fixture
def token():
    return create_access_token(user_id=uuid.uuid4(), email="t@example.com", name="T")


def test_rest_route_returns_results_when_save_fails(failing_db, bq_calls, token):
    async def fake_agent():
        return FakeAgent()
    app.dependency_overrides[query_routes.get_bioinfo_agent] = fake_agent
    try:
        r = TestClient(app).post(
            "/api/v1/query/research",
            json={"query": "metformin microbiome", "max_results": 5},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["literature_results"][0]["title"] == "P"
    assert body["metadata"]["history_saved"] is False


def test_websocket_sends_done_when_save_fails(monkeypatch, failing_db, bq_calls, token):
    monkeypatch.setattr(ws_routes, "_get_agent", lambda: FakeAgent())
    with TestClient(app).websocket_connect("/api/v1/ws/query") as ws:
        ws.send_json({"query": "metformin microbiome", "max_results": 5, "token": token})
        events = []
        while True:
            msg = ws.receive_json()
            events.append(msg["event"])
            if msg["event"] in ("done", "error"):
                break
    assert events[-1] == "done"
    assert msg["data"]["metadata"]["history_saved"] is False
