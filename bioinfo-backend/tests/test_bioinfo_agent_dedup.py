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


def _pubmed_article(title, doi, pmid="111"):
    return SimpleNamespace(title=title, authors=["X"], abstract="abs", journal="J",
                           publication_date=None, pmid=pmid, doi=doi, keywords=[],
                           publication_types=["Journal Article"], mesh_terms=[], trial_ids=[],
                           abstract_sections={})


class FakeICite:
    def __init__(self, data=None):
        self.data, self.calls = data or {}, []

    async def fetch(self, pmids):
        self.calls.append(list(pmids))
        return {p: self.data[p] for p in pmids if p in self.data}


class NoExtractor:
    available = False


class FakeSynth:
    def __init__(self):
        self.calls = []

    async def synthesize_summary(self, papers, original_query, evidence_summary=None):
        self.calls.append((papers, evidence_summary))
        return "summary"


def _agent(ncbi, preprints, **kw):
    kw.setdefault("embedding_service", ReverseScorer())
    kw.setdefault("icite_client", FakeICite())
    kw.setdefault("evidence_extractor", NoExtractor())
    kw.setdefault("response_synthesizer", FakeSynth())
    return BioinfoAgent(ncbi, preprint_client=preprints, **kw)


async def test_process_query_merges_scores_and_emits_events():
    agent = _agent(
        FakeNCBI([_pubmed_article("PubMed paper", "10.1/pm")]),
        FakePreprints({
            "biorxiv": [PreprintArticle("Bio preprint", [], "abs", "10.1101/b", None, "biorxiv")],
            "medrxiv": [PreprintArticle("PubMed paper", [], "abs", "10.1101/dup", None, "medrxiv")],
        }),
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
    agent = _agent(FakeNCBI([]), FakePreprints({}))
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


# ── Evidence step ────────────────────────────────────────────────────────────

from src.external.icite_client import CitationInfo  # noqa: E402
from src.services.evidence_extractor import FramedQuestion, PaperExtraction, RawEvidence  # noqa: E402


class FakeExtractor:
    available = True

    def __init__(self, framed=FramedQuestion(question="Does X work?", answerable=True)):
        self.framed = framed
        self.seen = None

    async def frame_question(self, query):
        return self.framed

    async def extract(self, framed, papers):
        self.seen = [p.ref for p in papers]
        item = PaperExtraction(index=1, design="cohort", organism="human", sample_size=50,
                               population=None, intervention=None, outcome=None,
                               stance="supports", key_finding="It works.", finding_quote="abs")
        return {0: RawEvidence(extraction=item, quote=None)}


def _events():
    events = []

    async def record(event, data=None):
        events.append(event)
    return events, record


async def test_evidence_and_citations_attached():
    icite = FakeICite({"111": CitationInfo("111", 42, 2.5, 1.0, 0.0, 0.0)})
    synth = FakeSynth()
    extractor = FakeExtractor()
    agent = _agent(
        FakeNCBI([_pubmed_article("A", "10.1/a", "111"), _pubmed_article("B", "10.1/b", "222")]),
        FakePreprints({}), icite_client=icite, evidence_extractor=extractor, response_synthesizer=synth,
    )
    events, record = _events()

    response = await agent.process_query(
        BioinformaticsQuery(query="does x work", max_results=5), query_id="q", progress_callback=record,
    )

    assert events[-2:] == ["extracting_evidence", "synthesizing"]
    papers = response.literature_results
    assert [p.ref for p in papers] == [1, 2]
    assert extractor.seen == [1, 2]
    assert papers[0].evidence.stance == "supports" and papers[1].evidence is None
    by_pmid = {p.pmid: p for p in papers}
    assert by_pmid["111"].citation_count == 42 and by_pmid["222"].citation_count is None
    assert [sorted(c) for c in icite.calls] == [["111", "222"]]
    assert response.evidence_summary.question == "Does X work?"
    assert response.evidence_summary.stance_counts == {"supports": 1}
    assert synth.calls[0][1] is response.evidence_summary


async def test_extractor_unavailable_still_gets_citations():
    icite = FakeICite({"111": CitationInfo("111", 7, None, 1.0, 0.0, 0.0)})
    agent = _agent(FakeNCBI([_pubmed_article("A", "10.1/a", "111")]), FakePreprints({}), icite_client=icite)
    events, record = _events()

    response = await agent.process_query(
        BioinformaticsQuery(query="does x work", max_results=5), query_id="q", progress_callback=record,
    )
    assert "extracting_evidence" not in events
    assert response.evidence_summary is None
    assert response.literature_results[0].citation_count == 7


async def test_framing_failure_means_no_evidence():
    agent = _agent(FakeNCBI([_pubmed_article("A", "10.1/a")]), FakePreprints({}),
                   evidence_extractor=FakeExtractor(framed=None))
    response = await agent.process_query(BioinformaticsQuery(query="does x work", max_results=5), query_id="q")
    assert response.evidence_summary is None
    assert response.literature_results[0].evidence is None


async def test_abstract_sections_not_serialized():
    article = _pubmed_article("A", "10.1/a")
    article.abstract_sections = {"RESULTS": "abs"}
    agent = _agent(FakeNCBI([article]), FakePreprints({}))
    response = await agent.process_query(BioinformaticsQuery(query="does x work", max_results=5), query_id="q")
    assert "abstract_sections" not in response.model_dump(mode="json")["literature_results"][0]
