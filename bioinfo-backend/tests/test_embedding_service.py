"""Unit tests for EmbeddingService.score_relevance with Vertex AI mocked out."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models.response_models import PaperResult
from src.services import embedding_service as es
from src.services.embedding_service import EmbeddingService


def _papers(n):
    return [PaperResult(title=f"Paper {i}", authors=[], abstract=f"abstract {i}") for i in range(n)]


class FakeEmbeddings(EmbeddingService):
    """Query vector is [1, 0]; document i gets a vector whose angle grows with i,
    except the ones listed in `best`, which point straight at the query."""

    def __init__(self, best=(), fail=False):
        super().__init__()
        self.best = set(best)
        self.fail = fail
        self.doc_batches = []

    async def get_embeddings(self, texts, task_type="RETRIEVAL_DOCUMENT"):
        if self.fail:
            return []
        if task_type == "RETRIEVAL_QUERY":
            return [[1.0, 0.0]]
        self.doc_batches.append(len(texts))
        return [[1.0, 0.0] if i in self.best else [1.0, float(i + 1)] for i in range(len(texts))]


class TestScoreRelevance:
    async def test_scores_set_and_sorted(self):
        papers = _papers(4)
        result = await FakeEmbeddings(best={2}).score_relevance("q", papers)

        scores = [p.relevance_score for p in result]
        assert all(s is not None and 0 <= s <= 1 for s in scores)
        assert scores == sorted(scores, reverse=True)
        assert result[0].title == "Paper 2"
        assert result[0].relevance_score == 1.0

    async def test_failure_returns_papers_unchanged(self):
        papers = _papers(3)
        result = await FakeEmbeddings(fail=True).score_relevance("q", papers)
        assert result == papers
        assert all(p.relevance_score is None for p in result)

    async def test_cap_limits_scored_papers(self):
        papers = _papers(es.EMBEDDING_CAP + 7)
        svc = FakeEmbeddings()
        result = await svc.score_relevance("q", papers)

        assert svc.doc_batches == [es.EMBEDDING_CAP]
        assert all(p.relevance_score is not None for p in result[:es.EMBEDDING_CAP])
        assert all(p.relevance_score is None for p in result[es.EMBEDDING_CAP:])
        assert [p.title for p in result[es.EMBEDDING_CAP:]] == [p.title for p in papers[es.EMBEDDING_CAP:]]

    async def test_empty_input(self):
        assert await FakeEmbeddings().score_relevance("q", []) == []

    async def test_does_not_mutate_input(self):
        papers = _papers(2)
        await FakeEmbeddings().score_relevance("q", papers)
        assert all(p.relevance_score is None for p in papers)


class TestGetEmbeddings:
    async def test_unconfigured_disables_after_first_failure(self, monkeypatch):
        svc = EmbeddingService()
        calls = []

        def boom():
            calls.append(1)
            raise RuntimeError("No GCP project configured for Vertex AI")

        monkeypatch.setattr(svc, "_get_model", boom)
        assert await svc.get_embeddings(["a"]) == []
        assert await svc.get_embeddings(["b"]) == []
        assert len(calls) == 1

    async def test_transient_error_does_not_disable(self, monkeypatch):
        svc = EmbeddingService()
        calls = []

        async def flaky(texts, task_type):
            calls.append(1)
            raise ConnectionError("timeout")

        monkeypatch.setattr(svc, "_embed_batch", flaky)
        assert await svc.get_embeddings(["a"]) == []
        assert await svc.get_embeddings(["b"]) == []
        assert len(calls) == 2

    async def test_batches_requests(self, monkeypatch):
        svc = EmbeddingService()
        sizes = []

        async def fake_batch(texts, task_type):
            sizes.append(len(texts))
            return [[0.1] for _ in texts]

        monkeypatch.setattr(svc, "_embed_batch", fake_batch)
        vecs = await svc.get_embeddings([str(i) for i in range(23)])
        assert len(vecs) == 23
        assert sorted(sizes, reverse=True) == [10, 10, 3]
