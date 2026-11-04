"""Unit tests for PreprintClient with an injected fake aiohttp session (no network)."""
import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.external.preprint_client import (
    EUROPE_PMC_SEARCH,
    PreprintClient,
    build_query,
    parse_record,
)


class FakeResponse:
    def __init__(self, payload=None, status=200, json_error=None):
        self._payload = payload
        self.status = status
        self._json_error = json_error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")

    async def json(self, content_type=None):
        if self._json_error:
            raise self._json_error
        return self._payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, params=None):
        self.calls.append((url, params))
        return self.response


def _record(**overrides):
    item = {
        "id": "PPR123",
        "source": "PPR",
        "title": "Base editing <i>in vivo</i>",
        "authorString": "Doe J, Smith A.",
        "authorList": {"author": [{"fullName": "Doe J"}, {"fullName": "Smith A"}]},
        "abstractText": "<h4>Background</h4>We edited &amp; measured.",
        "doi": "10.1101/2024.05.01.123456",
        "firstPublicationDate": "2024-05-01",
        "keywordList": {"keyword": ["CRISPR", "base editing"]},
    }
    item.update(overrides)
    return item


def _payload(*items):
    return {"hitCount": len(items), "resultList": {"result": list(items)}}


class TestSearch:
    async def test_parses_successful_response(self):
        session = FakeSession(FakeResponse(_payload(_record())))
        client = PreprintClient(session=session)

        [article] = await client.search("base editing", server="biorxiv")

        assert article.title == "Base editing in vivo"
        assert article.authors == ["Doe J", "Smith A"]
        assert article.abstract == "Background We edited & measured."
        assert article.doi == "10.1101/2024.05.01.123456"
        assert article.publication_date == datetime(2024, 5, 1)
        assert article.server == "biorxiv"
        assert article.keywords == ["CRISPR", "base editing"]

    async def test_request_targets_europe_pmc_with_server_filter(self):
        session = FakeSession(FakeResponse(_payload()))
        await PreprintClient(session=session).search("sepsis", server="medrxiv", max_results=5)

        url, params = session.calls[0]
        assert url == EUROPE_PMC_SEARCH
        assert 'PUBLISHER:"medRxiv"' in params["query"]
        assert "SRC:PPR" in params["query"]
        assert params["pageSize"] == "5"

    async def test_http_error_returns_empty(self):
        client = PreprintClient(session=FakeSession(FakeResponse(status=500)))
        assert await client.search("x y z", server="biorxiv") == []

    async def test_malformed_json_returns_empty(self):
        client = PreprintClient(session=FakeSession(FakeResponse(json_error=ValueError("bad json"))))
        assert await client.search("x y z", server="biorxiv") == []

    async def test_unexpected_shape_returns_empty(self):
        client = PreprintClient(session=FakeSession(FakeResponse({"unexpected": True})))
        assert await client.search("x y z", server="biorxiv") == []

    async def test_max_results_truncates(self):
        items = [_record(title=f"Paper {i}", doi=f"10.1101/{i}") for i in range(8)]
        client = PreprintClient(session=FakeSession(FakeResponse(_payload(*items))))
        assert len(await client.search("x y z", server="biorxiv", max_results=3)) == 3

    async def test_malformed_record_skipped(self):
        items = [_record(firstPublicationDate="not-a-date"), _record(title="Good one")]
        client = PreprintClient(session=FakeSession(FakeResponse(_payload(*items))))
        result = await client.search("x y z", server="biorxiv")
        assert [a.title for a in result] == ["Good one"]

    async def test_unknown_server_rejected(self):
        with pytest.raises(ValueError):
            await PreprintClient(session=FakeSession(FakeResponse(_payload()))).search("x", server="arxiv")


class TestParsing:
    def test_falls_back_to_author_string(self):
        article = parse_record(_record(authorList=None), "biorxiv")
        assert article.authors == ["Doe J", "Smith A"]

    def test_missing_optional_fields(self):
        article = parse_record({"title": "Only a title"}, "medrxiv")
        assert article.authors == []
        assert article.abstract == ""
        assert article.doi == ""
        assert article.publication_date is None


class TestBuildQuery:
    def test_date_range_converted(self):
        q = build_query("CRISPR", "biorxiv", min_date="2023/01/01", max_date="2024/12/31")
        assert "FIRST_PDATE:[2023-01-01 TO 2024-12-31]" in q

    def test_open_ended_date_range(self):
        q = build_query("CRISPR", "biorxiv", min_date="2023/06/01")
        assert "FIRST_PDATE:[2023-06-01 TO 3000-12-31]" in q

    def test_no_dates_no_date_clause(self):
        assert "FIRST_PDATE" not in build_query("CRISPR", "biorxiv")

    def test_unbalanced_quote_removed(self):
        assert build_query('"gene editing', "biorxiv").startswith("(gene editing)")

    def test_balanced_quotes_kept(self):
        assert build_query('"gene editing"', "biorxiv").startswith('("gene editing")')
