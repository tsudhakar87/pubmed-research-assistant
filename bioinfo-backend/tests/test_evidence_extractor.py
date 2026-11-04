"""Tests for EvidenceExtractor and build_evidence with a fake Gemini client."""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.external.data_parser import NO_ABSTRACT
from src.external.icite_client import CitationInfo
from src.models.response_models import PaperResult
from src.services import evidence_extractor as ee
from src.services.evidence_extractor import (
    EvidenceExtractor,
    ExtractionBatch,
    FramedQuestion,
    PaperExtraction,
    RawEvidence,
    build_evidence,
    verify_quote,
)

ABSTRACT = "We randomized 240 adults to metformin or placebo. Metformin increased A. muciniphila abundance 2.1-fold (p<0.001)."
QUOTE = "Metformin increased A. muciniphila abundance 2.1-fold (p<0.001)."


def _paper(i=0, abstract=ABSTRACT, **kw):
    return PaperResult(title=f"Paper {i}", authors=[], abstract=abstract,
                       publication_date=datetime(2020 + i % 5, 1, 1), **kw)


def _item(index, quote=QUOTE, stance="supports", **kw):
    base = dict(index=index, design="rct", organism="human", sample_size=240, population="adults",
                intervention="metformin", outcome="A. muciniphila", stance=stance,
                key_finding="Metformin raised Akkermansia.", finding_quote=quote)
    base.update(kw)
    return PaperExtraction(**base)


class FakeGemini:
    """Returns queued responses per schema; records prompts."""

    def __init__(self, framed=None, batches=None, available=True):
        self.framed = framed
        self.batches = list(batches or [])
        self.prompts = []
        self.available = available

    async def generate_json(self, prompt, schema, **kw):
        self.prompts.append((schema.__name__, prompt))
        if schema is FramedQuestion:
            return self.framed
        result = self.batches.pop(0) if self.batches else None
        return result(prompt) if callable(result) else result


QUESTION = FramedQuestion(question="Does metformin alter the gut microbiome?", answerable=True)


class TestVerifyQuote:
    def test_exact(self):
        assert verify_quote(QUOTE, ABSTRACT) == QUOTE

    def test_ignores_case_spacing_and_quote_style(self):
        abstract = "Patients said it was “better” – overall  outcomes improved markedly."
        assert verify_quote('patients said it was "better" - overall outcomes improved markedly', abstract)

    def test_paraphrase_rejected(self):
        assert verify_quote("Metformin doubled Akkermansia levels in adults.", ABSTRACT) is None

    def test_too_short_rejected(self):
        assert verify_quote("Metformin", ABSTRACT) is None

    def test_trailing_period_tolerated(self):
        assert verify_quote("We randomized 240 adults to metformin or placebo", ABSTRACT)


class TestExtract:
    async def test_maps_items_back_to_papers(self):
        papers = [_paper(0), _paper(1, abstract=NO_ABSTRACT), _paper(2)]
        gemini = FakeGemini(batches=[ExtractionBatch(papers=[_item(1), _item(2, stance="no_effect")])])

        result = await EvidenceExtractor(gemini).extract(QUESTION, papers)

        assert sorted(result) == [0, 2]  # paper without abstract skipped
        assert result[0].extraction.stance == "supports"
        assert result[2].extraction.stance == "no_effect"
        assert result[0].quote == QUOTE

    async def test_unverified_quote_kept_but_flagged(self):
        gemini = FakeGemini(batches=[ExtractionBatch(papers=[_item(1, quote="Something the abstract never says at all.")])])
        result = await EvidenceExtractor(gemini).extract(QUESTION, [_paper()])
        assert result[0].quote is None

    async def test_bad_and_duplicate_indexes_ignored(self):
        gemini = FakeGemini(batches=[ExtractionBatch(papers=[_item(0), _item(5), _item(1), _item(1, stance="contradicts")])])
        result = await EvidenceExtractor(gemini).extract(QUESTION, [_paper()])
        assert list(result) == [0] and result[0].extraction.stance == "supports"

    async def test_failed_batch_only_loses_its_papers(self, monkeypatch):
        monkeypatch.setattr(ee, "BATCH_SIZE", 2)
        papers = [_paper(i) for i in range(4)]
        gemini = FakeGemini(batches=[None, ExtractionBatch(papers=[_item(1), _item(2)])])
        result = await EvidenceExtractor(gemini).extract(QUESTION, papers)
        assert sorted(result) == [2, 3]

    async def test_caps_number_of_papers(self, monkeypatch):
        monkeypatch.setattr(ee, "MAX_PAPERS", 3)
        monkeypatch.setattr(ee, "BATCH_SIZE", 10)
        gemini = FakeGemini(batches=[ExtractionBatch(papers=[])])
        await EvidenceExtractor(gemini).extract(QUESTION, [_paper(i) for i in range(6)])
        prompt = gemini.prompts[0][1]
        assert "[3] Paper 2" in prompt and "[4]" not in prompt

    async def test_topic_query_forces_not_applicable(self):
        topic = FramedQuestion(question="CRISPR off-target rates", answerable=False)
        gemini = FakeGemini(batches=[ExtractionBatch(papers=[_item(1, stance="supports")])])
        result = await EvidenceExtractor(gemini).extract(topic, [_paper()])
        assert result[0].extraction.stance == "not_applicable"
        assert 'always "not_applicable"' in gemini.prompts[0][1]

    async def test_prompt_includes_metadata_and_sections(self):
        paper = _paper(publication_types=["Randomized Controlled Trial"], mesh_terms=["Humans"],
                       abstract_sections={"METHODS": "We randomized 240 adults.", "RESULTS": QUOTE},
                       source="pubmed")
        preprint = _paper(1, source="biorxiv")
        gemini = FakeGemini(batches=[ExtractionBatch(papers=[])])
        await EvidenceExtractor(gemini).extract(QUESTION, [paper, preprint])
        prompt = gemini.prompts[0][1]
        assert "Publication types: Randomized Controlled Trial" in prompt
        assert "MeSH: Humans" in prompt
        assert "METHODS: We randomized" in prompt
        assert "Preprint (not peer reviewed)" in prompt
        assert QUESTION.question in prompt


class TestFrameQuestion:
    async def test_returns_framing(self):
        assert await EvidenceExtractor(FakeGemini(framed=QUESTION)).frame_question("metformin microbiome") == QUESTION

    async def test_failure_returns_none(self):
        assert await EvidenceExtractor(FakeGemini(framed=None)).frame_question("x") is None

    async def test_blank_question_returns_none(self):
        blank = FramedQuestion(question="  ", answerable=True)
        assert await EvidenceExtractor(FakeGemini(framed=blank)).frame_question("x") is None


class TestBuildEvidence:
    def _raw(self, **kw):
        return RawEvidence(extraction=_item(1, **kw), quote=QUOTE)

    def test_pubmed_labels_override_ai(self):
        paper = _paper(publication_types=["Meta-Analysis"], mesh_terms=["Humans"])
        ev = build_evidence(self._raw(design="rct", organism="animal"), paper)
        assert (ev.design, ev.design_source) == ("meta_analysis", "pubmed")
        assert (ev.organism, ev.organism_source) == ("human", "pubmed")

    def test_mesh_animal_sets_design_when_pubtypes_silent(self):
        paper = _paper(publication_types=["Journal Article"], mesh_terms=["Animals", "Mice"])
        ev = build_evidence(self._raw(design="rct", organism="human"), paper)
        assert (ev.design, ev.design_source) == ("animal", "pubmed")
        assert ev.organism == "animal"

    def test_icite_fallback_for_organism(self):
        cite = CitationInfo("1", 10, 1.2, human=0.0, animal=0.9, molecular_cellular=0.1)
        ev = build_evidence(self._raw(design="cohort", organism="human"), _paper(), cite)
        assert (ev.organism, ev.organism_source) == ("animal", "icite")
        assert (ev.design, ev.design_source) == ("cohort", "ai")

    def test_ai_used_when_no_metadata(self):
        ev = build_evidence(self._raw(design="cohort", organism="human"), _paper())
        assert (ev.design_source, ev.organism_source) == ("ai", "ai")

    def test_verified_flag_and_sample_size(self):
        raw = RawEvidence(extraction=_item(1, sample_size=0), quote=None)
        ev = build_evidence(raw, _paper())
        assert ev.verified is False and ev.finding_quote is None
        assert ev.sample_size is None


class TestReviewStance:
    """Phase 0: Gemini labeled narrative reviews "supports"; code overrides that."""

    def _raw(self, stance="supports", design="review"):
        return RawEvidence(extraction=_item(1, stance=stance, design=design), quote=QUOTE)

    def test_pubmed_review_forced_not_applicable(self):
        ev = build_evidence(self._raw(), _paper(publication_types=["Journal Article", "Review"]))
        assert (ev.design, ev.stance) == ("review", "not_applicable")
        assert ev.key_finding  # finding is still shown

    def test_ai_labeled_review_forced_too(self):
        ev = build_evidence(self._raw(design="review"), _paper())
        assert ev.stance == "not_applicable"

    def test_meta_analysis_keeps_stance(self):
        ev = build_evidence(self._raw(design="meta_analysis"), _paper(publication_types=["Review", "Meta-Analysis"]))
        assert (ev.design, ev.stance) == ("meta_analysis", "supports")

    def test_systematic_review_keeps_stance(self):
        ev = build_evidence(self._raw(stance="no_effect"), _paper(publication_types=["Systematic Review"]))
        assert ev.stance == "no_effect"
