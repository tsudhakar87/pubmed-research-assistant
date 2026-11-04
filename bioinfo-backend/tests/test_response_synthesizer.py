"""Tests for grounded synthesis prompts and citation sanitizing."""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.agents.response_synthesizer import (
    FAILED,
    UNAVAILABLE,
    ResponseSynthesizer,
    sanitize_citations,
)
from src.models.response_models import Evidence, PaperResult
from src.services.evidence_aggregator import summarize


class FakeGemini:
    def __init__(self, reply="Overall it helps [1] but not in mice [2, 9].", available=True):
        self.reply, self.available, self.prompts = reply, available, []

    async def generate_text(self, prompt, **kw):
        self.prompts.append(prompt)
        return self.reply


def _paper(ref, stance="supports", organism="human", n=100, source="pubmed", evidence=True):
    ev = Evidence(design="rct" if organism == "human" else "animal", design_source="pubmed",
                  organism=organism, organism_source="pubmed", sample_size=n, stance=stance,
                  key_finding=f"finding {ref}", population="adults") if evidence else None
    return PaperResult(title=f"Paper {ref}", authors=[], abstract=f"abstract {ref}", ref=ref,
                       source=source, publication_date=datetime(2020 + ref, 1, 1), evidence=ev)


class TestSanitizeCitations:
    def test_drops_unknown_refs(self):
        assert sanitize_citations("A [1] and B [2, 9].", [1, 2]) == "A [1] and B [2]."

    def test_removes_empty_brackets(self):
        assert sanitize_citations("Claim [7].", [1, 2]) == "Claim."

    def test_expands_ranges(self):
        assert sanitize_citations("See [1-3].", [1, 2, 3, 4]) == "See [1, 2, 3]."

    def test_dedupes(self):
        assert sanitize_citations("X [2, 2, 1].", [1, 2]) == "X [2, 1]."

    def test_leaves_other_brackets_alone(self):
        assert sanitize_citations("Dose [mg/kg] matters [1].", [1]) == "Dose [mg/kg] matters [1]."


class TestSynthesize:
    async def test_grounded_prompt_uses_computed_facts(self):
        papers = [_paper(1), _paper(2, "no_effect", "animal", 24), _paper(3, "supports", source="biorxiv")]
        summary = summarize(papers, "Does metformin alter the gut microbiome?", True)
        gemini = FakeGemini()

        text = await ResponseSynthesizer(gemini).synthesize_summary(papers, "metformin microbiome", summary)

        prompt = gemini.prompts[0]
        assert 'Answer the question "Does metformin alter the gut microbiome?"' in prompt
        assert "Stance counts: 1 no_effect, 2 supports" in prompt
        assert "[2] 2022 | animal study | animal | n=24 | stance: no_effect" in prompt
        assert "| PREPRINT |" in prompt
        assert "abstract 1" not in prompt  # grounded mode sends the table, not raw abstracts
        assert text == "Overall it helps [1] but not in mice [2]."

    async def test_topic_prompt(self):
        papers = [_paper(1, "not_applicable")]
        summary = summarize(papers, "CRISPR off-target rates", False)
        gemini = FakeGemini()
        await ResponseSynthesizer(gemini).synthesize_summary(papers, "q", summary)
        assert 'searched the topic "CRISPR off-target rates"' in gemini.prompts[0]
        assert "Stance counts" not in gemini.prompts[0]

    async def test_fallback_without_evidence(self):
        papers = [_paper(1, evidence=False), _paper(2, evidence=False)]
        gemini = FakeGemini()
        await ResponseSynthesizer(gemini).synthesize_summary(papers, "metformin microbiome", None)
        assert "[1] Paper 1 (2021)\nabstract 1" in gemini.prompts[0]

    async def test_unavailable(self):
        result = await ResponseSynthesizer(FakeGemini(available=False)).synthesize_summary([_paper(1)], "q")
        assert result == UNAVAILABLE

    async def test_generation_failure(self):
        result = await ResponseSynthesizer(FakeGemini(reply=None)).synthesize_summary([_paper(1)], "q")
        assert result == FAILED

    async def test_no_papers(self):
        assert await ResponseSynthesizer(FakeGemini()).synthesize_summary([], "q") is None
