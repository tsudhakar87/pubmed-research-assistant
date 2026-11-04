"""Unit tests for BioinfoAgent merge/dedup/cap and the parallel search pipeline."""
import os
import sys
from datetime import datetime
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.agents.bioinfo_agent import BioinfoAgent
from src.external.preprint_client import PreprintArticle
from src.models.request_models import BioinformaticsQuery
from src.models.response_models import PaperResult


def _paper(title, doi=None, source="pubmed", pmid="1"):
    return PaperResult(title=title, authors=[], doi=doi, source=source,
                       pmid=pmid if source == "pubmed" else None)


merge = BioinfoAgent._merge_and_dedup


class TestMergeAndDedup:
    def test_doi_collision_drops_preprint(self):
        pubmed = [_paper("Published title", doi="10.1/ABC")]
        preprints = [_paper("Different preprint title", doi="10.1/abc", source="biorxiv")]
        assert merge(pubmed, preprints) == pubmed

    def test_title_collision_drops_preprint(self):
        pubmed = [_paper("CRISPR screens in T cells.", doi="10.1/journal")]
        preprints = [_paper("CRISPR Screens in T-cells", doi="10.1101/preprint", source="biorxiv")]
        # "t-cells" normalizes to "tcells", "T cells" to "t cells" — not equal, so kept
        assert len(merge(pubmed, preprints)) == 2

        preprints = [_paper("crispr screens in t cells", doi="10.1101/preprint", source="biorxiv")]
        assert merge(pubmed, preprints) == pubmed

    def test_title_collision_without_doi(self):
        pubmed = [_paper("Gut microbiome and metformin")]
        preprints = [_paper("Gut Microbiome and Metformin!", source="medrxiv")]
        assert merge(pubmed, preprints) == pubmed

    def test_no_collision_keeps_both_pubmed_first(self):
        pubmed = [_paper("A", doi="10.1/a")]
        preprints = [_paper("B", doi="10.1101/b", source="biorxiv")]
        assert [p.title for p in merge(pubmed, preprints)] == ["A", "B"]

    def test_empty_preprints(self):
        pubmed = [_paper("A"), _paper("B")]
        assert merge(pubmed, []) == pubmed

    def test_duplicate_preprints_across_servers(self):
        preprints = [
            _paper("Same study", doi="10.1101/x", source="biorxiv"),
            _paper("Same study", doi="10.1101/x", source="medrxiv"),
        ]
        assert len(merge([], preprints)) == 1

    def test_empty_doi_never_matches(self):
        pubmed = [_paper("A", doi="")]
        preprints = [_paper("B", doi="", source="biorxiv")]
        assert len(merge(pubmed, preprints)) == 2


class TestSoftCap:
    def test_caps_at_150_percent(self):
        papers = [_paper(str(i)) for i in range(40)]
        assert len(BioinfoAgent._soft_cap(papers, 20)) == 30

    def test_shorter_list_untouched(self):
        papers = [_paper(str(i)) for i in range(5)]
        assert len(BioinfoAgent._soft_cap(papers, 20)) == 5


class TestPreprintConversion:
    def test_preprint_fields(self):
        [p] = BioinfoAgent._convert_preprints_to_paper_results([PreprintArticle(
            title="T", authors=["A"], abstract="", doi="10.1101/x",
            publication_date=datetime(2024, 1, 1), server="medrxiv",
        )])
        assert p.source == "medrxiv"
        assert p.pmid is None
        assert p.journal == "medRxiv"
        assert p.abstract is None  # empty string becomes None


# ── Pipeline (process_query) with fakes ─────────────────────────────────────

class FakeNCBI:
    def __init__(self, articles):
        self.articles = articles

    async def search_and_fetch(self, query, max_results=20, **kwargs):
        return self.articles


class FakePreprints:
    def __init__(self, by_server):
        self.by_server = by_server
        self.calls = []

    async def search(self, query, server, max_results=10, min_date=None, max_date=None):
        self.calls.append((server, max_results))
        return self.by_server.get(server, [])


class ReverseScorer:
    """Stands in for EmbeddingService: scores by reversed position."""
    async def score_relevance(self, query, papers):
        n = len(papers)
        scored = [p.model_copy(update={"relevance_score": (i + 1) / n}) for i, p in enumerate(papers)]
        return sorted(scored, key=lambda p: p.relevance_score, reverse=True)


def _pubmed_article(title, doi):
    return SimpleNamespace(title=title, authors=["X"], abstract="abs", journal="J",
                           publication_date=None, pmid="111", doi=doi, keywords=[])


async def test_process_query_merges_scores_and_emits_events():
    agent = BioinfoAgent(
        FakeNCBI([_pubmed_article("PubMed paper", "10.1/pm")]),
        preprint_client=FakePreprints({
            "biorxiv": [PreprintArticle("Bio preprint", [], "abs", "10.1101/b", None, "biorxiv")],
            "medrxiv": [PreprintArticle("PubMed paper", [], "abs", "10.1101/dup", None, "medrxiv")],
        }),
        embedding_service=ReverseScorer(),
    )
    events = []

    async def record(event, data=None):
        events.append(event)

    response = await agent.process_query(
        BioinformaticsQuery(query="test query here", max_results=5),
        query_id="q_test",
        include_ai_summary=False,
        progress_callback=record,
    )

    assert events == [
        "classifying", "searching_pubmed", "searching_preprints",
        "retrieving_abstracts", "scoring_relevance",
    ]
    # The medRxiv record duplicates the PubMed title and is dropped
    assert [p.title for p in response.literature_results] == ["Bio preprint", "PubMed paper"]
    assert [p.source for p in response.literature_results] == ["biorxiv", "pubmed"]
    assert agent.preprint_client.calls == [("biorxiv", 5), ("medrxiv", 5)]


async def test_process_query_no_results_skips_scoring():
    agent = BioinfoAgent(FakeNCBI([]), preprint_client=FakePreprints({}),
                         embedding_service=ReverseScorer())
    events = []

    async def record(event, data=None):
        events.append(event)

    response = await agent.process_query(
        BioinformaticsQuery(query="nothing matches", max_results=10),
        query_id="q_empty", include_ai_summary=True, progress_callback=record,
    )
    assert response.literature_results == []
    assert "scoring_relevance" not in events
    assert "synthesizing" not in events
