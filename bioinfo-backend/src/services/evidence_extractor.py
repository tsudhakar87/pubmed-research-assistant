"""
Per-paper evidence extraction with Gemini structured output.

1. frame_question(): turn the user's query into a yes/no evidence question, or
   decide it is a topic with no single question (answerable=False).
2. extract(): for the top papers with abstracts, ask Gemini for design, organism,
   sample size, population/intervention/outcome, stance and a key finding with a
   verbatim quote. Batches run in parallel; a failed batch only loses its papers.
3. Quotes are checked against the abstract. A quote that isn't really there is
   dropped and the paper is marked unverified.
4. build_evidence(): curated PubMed/iCite labels override the model's design and
   organism wherever they exist.
"""
import asyncio
import logging
import re
import unicodedata
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from ..external.data_parser import NO_ABSTRACT
from ..external.icite_client import CitationInfo
from ..models.response_models import Design, Evidence, OrganismLabel, PaperResult, Stance
from ..utils.study_design import (
    design_for_organism,
    design_from_pubtypes,
    organism_from_icite,
    organism_from_mesh,
)
from .gemini_client import GeminiClient, get_gemini_client

logger = logging.getLogger(__name__)

MAX_PAPERS = 30
BATCH_SIZE = 10
_MAX_ABSTRACT_CHARS = 3000


# ── Gemini response schemas ──────────────────────────────────────────────────

class FramedQuestion(BaseModel):
    question: str = Field(description="The query rewritten as one yes/no evidence question, or a short topic statement")
    answerable: bool = Field(description="False if the query is a topic with no single yes/no question")


class PaperExtraction(BaseModel):
    index: int = Field(description="The [n] number of the paper in this prompt")
    design: Design
    organism: OrganismLabel
    sample_size: Optional[int] = Field(description="Number of participants/animals/samples, only if stated; else null")
    population: Optional[str] = Field(description="Who or what was studied, a few words")
    intervention: Optional[str] = Field(description="Exposure or intervention, a few words")
    outcome: Optional[str] = Field(description="Main outcome measured, a few words")
    stance: Stance
    key_finding: str = Field(description="Main result in plain language, at most 25 words")
    finding_quote: str = Field(description="The sentence or clause from the abstract that states the result, copied exactly")


class ExtractionBatch(BaseModel):
    papers: List[PaperExtraction]


# ── Helpers ──────────────────────────────────────────────────────────────────

_QUOTE_CHARS = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "−": "-"})


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "").translate(_QUOTE_CHARS).lower()
    return re.sub(r"\s+", " ", t).strip()


def verify_quote(quote: str, abstract: str) -> Optional[str]:
    """The quote if it appears in the abstract (ignoring case, spacing, quote/dash style), else None."""
    q = _norm(quote).strip(" .;:,\"'")
    if len(q) < 12:
        return None
    return quote.strip() if q in _norm(abstract) else None


def has_abstract(paper: PaperResult) -> bool:
    return bool(paper.abstract) and paper.abstract != NO_ABSTRACT


def _abstract_for_prompt(paper: PaperResult) -> str:
    if paper.abstract_sections:
        text = "\n".join(f"{label}: {body}" for label, body in paper.abstract_sections.items())
    else:
        text = paper.abstract or ""
    return text[:_MAX_ABSTRACT_CHARS]


def _framing_prompt(query: str) -> str:
    return f"""A researcher searched biomedical literature for: "{query}"

If the search implies a question that individual studies can answer yes or no (does X affect Y, is X associated with Y, does X work for Y), rewrite it as ONE clear yes/no question and set answerable=true. Keep the researcher's scope; do not add populations or outcomes they did not mention.

If it is a topic or a request for measurements or methods (e.g. "CRISPR off-target rates", "single-cell sequencing methods"), restate it as a short topic and set answerable=false."""


def _extraction_prompt(question: str, answerable: bool, papers: List[PaperResult]) -> str:
    stance_rule = (
        f'stance: does this paper\'s result support a "yes" answer to the question "{question}"? '
        'Use "supports", "contradicts", "mixed" (some outcomes yes, some no), '
        '"no_effect" (tested and found no significant effect), or "not_applicable" '
        "(the paper does not test the question, e.g. a review without new data or an unrelated outcome)."
        if answerable else
        'stance: always "not_applicable" (this search is a topic, not a yes/no question).'
    )
    blocks = []
    for i, p in enumerate(papers, 1):
        meta = []
        if p.publication_types:
            meta.append("Publication types: " + ", ".join(p.publication_types))
        if p.mesh_terms:
            meta.append("MeSH: " + ", ".join(p.mesh_terms[:25]))
        if p.source in ("biorxiv", "medrxiv"):
            meta.append("Preprint (not peer reviewed)")
        year = p.publication_date.year if p.publication_date else "unknown"
        blocks.append(
            f"[{i}] {p.title} ({year})\n" + "".join(f"{m}\n" for m in meta) +
            f"Abstract:\n{_abstract_for_prompt(p)}"
        )
    papers_text = "\n\n".join(blocks)
    return f"""You are extracting structured evidence from biomedical abstracts. Use ONLY what each abstract states. Do not use outside knowledge.

Question: {question}

For every paper below, return one entry with its [n] as index:
- design: the study design. Use "animal" or "in_vitro" for non-human lab studies; "review" for narrative reviews.
- organism: "human", "animal", "in_vitro" (cells, organoids, biochemical), "mixed", or "unknown".
- sample_size: the number of participants, animals or samples ONLY if the abstract states it. Otherwise null. Never estimate.
- population, intervention, outcome: a few words each, or null if not stated.
- {stance_rule}
- key_finding: the main result in plain language, at most 25 words.
- finding_quote: copy, exactly and in full, the sentence or clause from the abstract that states that result. Do not paraphrase, shorten with "...", or fix typos.

Papers:

{papers_text}"""


# ── Extractor ────────────────────────────────────────────────────────────────

class RawEvidence(BaseModel):
    """A validated model extraction for one paper, before metadata overrides."""
    extraction: PaperExtraction
    quote: Optional[str]


class EvidenceExtractor:
    def __init__(self, gemini: Optional[GeminiClient] = None):
        self.gemini = gemini or get_gemini_client()

    @property
    def available(self) -> bool:
        return self.gemini.available

    async def frame_question(self, query: str) -> Optional[FramedQuestion]:
        framed = await self.gemini.generate_json(_framing_prompt(query), FramedQuestion, max_tokens=512)
        if framed is None or not framed.question.strip():
            return None
        return framed

    async def _extract_batch(
        self, framed: FramedQuestion, papers: List[PaperResult]
    ) -> List[Optional[RawEvidence]]:
        result = await self.gemini.generate_json(
            _extraction_prompt(framed.question, framed.answerable, papers), ExtractionBatch
        )
        out: List[Optional[RawEvidence]] = [None] * len(papers)
        if result is None:
            return out
        for item in result.papers:
            i = item.index - 1
            if not 0 <= i < len(papers) or out[i] is not None:
                continue  # out of range or duplicate index: ignore
            if not framed.answerable:
                item = item.model_copy(update={"stance": "not_applicable"})
            out[i] = RawEvidence(extraction=item, quote=verify_quote(item.finding_quote, papers[i].abstract or ""))
        return out

    async def extract(
        self, framed: FramedQuestion, papers: List[PaperResult]
    ) -> Dict[int, RawEvidence]:
        """
        Extract evidence for the first MAX_PAPERS papers that have abstracts.
        Returns {position in `papers`: RawEvidence}; papers that failed or were skipped are absent.
        """
        targets = [i for i, p in enumerate(papers) if has_abstract(p)][:MAX_PAPERS]
        batches = [targets[i:i + BATCH_SIZE] for i in range(0, len(targets), BATCH_SIZE)]
        results = await asyncio.gather(*(
            self._extract_batch(framed, [papers[i] for i in batch]) for batch in batches
        ))
        extracted: Dict[int, RawEvidence] = {}
        for batch, batch_result in zip(batches, results):
            for pos, raw in zip(batch, batch_result):
                if raw is not None:
                    extracted[pos] = raw
        return extracted


def build_evidence(
    raw: RawEvidence, paper: PaperResult, citation: Optional[CitationInfo] = None
) -> Evidence:
    """Combine the model's extraction with curated labels. Precedence: PubMed, then iCite, then AI."""
    ex = raw.extraction

    organism, organism_source = ex.organism, "ai"
    pubmed_design = design_from_pubtypes(paper.publication_types)
    mesh_organism = organism_from_mesh(paper.mesh_terms, pubmed_design)
    if mesh_organism:
        organism, organism_source = mesh_organism, "pubmed"
    elif citation:
        icite_organism = organism_from_icite(citation.human, citation.animal, citation.molecular_cellular)
        if icite_organism:
            organism, organism_source = icite_organism, "icite"

    design: str = ex.design
    design_source: Literal["pubmed", "ai"] = "ai"
    if pubmed_design:
        design, design_source = pubmed_design, "pubmed"
    elif organism_source == "pubmed" and design_for_organism(organism):
        # MeSH says animal or cell work and the publication types name no design
        design, design_source = design_for_organism(organism), "pubmed"

    sample_size = ex.sample_size if ex.sample_size and ex.sample_size > 0 else None

    # Narrative reviews summarize others' work; they don't test the question themselves.
    # Models often label them "supports" anyway (seen in Phase 0), which would inflate
    # the counts, so this is enforced in code. Systematic reviews and meta-analyses
    # pool data and keep their stance.
    stance = "not_applicable" if design == "review" else ex.stance

    return Evidence(
        design=design,
        design_source=design_source,
        organism=organism,
        organism_source=organism_source,
        sample_size=sample_size,
        population=ex.population or None,
        intervention=ex.intervention or None,
        outcome=ex.outcome or None,
        stance=stance,
        key_finding=ex.key_finding.strip(),
        finding_quote=raw.quote,
        verified=raw.quote is not None,
    )
