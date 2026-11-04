"""Tests for ICiteClient with a fake aiohttp session (no network)."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.external import icite_client
from src.external.icite_client import ICITE_PUBS, ICiteClient

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "icite_pubs_sample.json").read_text())


class FakeResponse:
    def __init__(self, payload=None, status=200):
        self._payload, self.status = payload, status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")

    async def json(self, content_type=None):
        return self._payload


class FakeSession:
    def __init__(self, payload=None, status=200):
        self.payload, self.status, self.calls = payload, status, []

    def get(self, url, params=None):
        self.calls.append((url, params))
        return FakeResponse(self.payload, self.status)


async def test_parses_fixture():
    session = FakeSession(FIXTURE)
    result = await ICiteClient(session=session).fetch(["39000001", "39000002"])

    a = result["39000001"]
    assert (a.citation_count, a.relative_citation_ratio, a.human) == (212, 3.12, 1.0)
    b = result["39000002"]
    assert b.relative_citation_ratio is None
    assert (b.animal, b.molecular_cellular) == (0.75, 0.25)

    url, params = session.calls[0]
    assert url == ICITE_PUBS
    assert params["pmids"] == "39000001,39000002"


async def test_unknown_pmid_absent():
    result = await ICiteClient(session=FakeSession(FIXTURE)).fetch(["39000001", "99999999"])
    assert "99999999" not in result


async def test_http_error_returns_empty():
    assert await ICiteClient(session=FakeSession(status=503)).fetch(["1"]) == {}


async def test_malformed_record_skipped():
    payload = {"data": [{"citation_count": 5}, {"pmid": 7, "citation_count": "3"}]}
    result = await ICiteClient(session=FakeSession(payload)).fetch(["7"])
    assert list(result) == ["7"] and result["7"].citation_count == 3


async def test_empty_input_makes_no_request():
    session = FakeSession(FIXTURE)
    assert await ICiteClient(session=session).fetch([]) == {}
    assert session.calls == []


async def test_batches_and_dedupes(monkeypatch):
    monkeypatch.setattr(icite_client, "BATCH_SIZE", 2)
    session = FakeSession({"data": []})
    await ICiteClient(session=session).fetch(["1", "2", "2", "3", "", "4", "5"])
    assert [p["pmids"] for _, p in session.calls] == ["1,2", "3,4", "5"]
