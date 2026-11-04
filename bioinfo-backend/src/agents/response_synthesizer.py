"""
AI synthesis of research results.

Grounded mode (when an EvidenceSummary exists): Gemini writes from the per-paper
extraction table and the counts/gaps computed in code. It is told to reuse those
numbers, not recount, and to cite papers as [n] using their `ref` numbers.

Fallback mode (no evidence, e.g. extraction failed): summarizes the top abstracts,
still citing [n].

Citations are sanitized afterwards so the UI never links to a paper that doesn't exist.
"""
import re
from typing import Iterable, List, Optional

from ..models.response_models import EvidenceSummary, PaperResult
from ..services.gemini_client import GeminiClient, get_gemini_client

UNAVAILABLE = "[AI summary unavailable - Vertex AI not configured]"
FAILED = "AI summary could not be generated. Try regenerate."

_FALLBACK_PAPERS = 8
_FALLBACK_ABSTRACT_CHARS = 700
_CITATION_RE = re.compile(r"\[(\d+(?:\s*[,–-]\s*\d+)*)\]")

_DESIGN_NAMES = {
    "meta_analysis": "meta-analysis", "systematic_review": "systematic review", "rct": "RCT",
    "clinical_trial": "clinical trial", "cohort": "cohort", "case_control": "case-control",
    "cross_sectional": "cross-sectional", "observational": "observational",
    "case_report": "case report", "review": "review", "animal": "animal study",
    "in_vitro": "in vitro", "other": "other",
}

_STYLE_RULES = """Write plain text only: no markdown, no headings, no bullet points.
Cite papers with their numbers in square brackets right after each claim, e.g. [3] or [2, 7].
Only cite numbers that appear in the list. Do not invent studies, numbers or findings.
Keep it to about 200 words."""


def sanitize_citations(text: str, valid_refs: Iterable[int]) -> str:
    """Drop citation numbers that don't exist; remove brackets left empty; tidy spacing."""
    valid = set(valid_refs)

    def fix(match: re.Match) -> str:
        nums: List[int] = []
        for part in re.split(r"\s*,\s*", match.group(1)):
            bounds = [int(x) for x in re.split(r"\s*[–-]\s*", part)]
            rng = range(bounds[0], bounds[-1] + 1) if len(bounds) == 2 and bounds[1] - bounds[0] < 20 else bounds
            nums.extend(n for n in rng if n in valid and n not in nums)
        return f"[{', '.join(map(str, nums))}]" if nums else ""

    cleaned = _CITATION_RE.sub(fix, text)
    cleaned = re.sub(r"[ \t]+([.,;:])", r"\1", cleaned)
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def _refs(papers: List[PaperResult]) -> List[int]:
    return [p.ref if p.ref is not None else i for i, p in enumerate(papers, 1)]


def _evidence_table(papers: List[PaperResult]) -> str:
    rows = []
    for ref, p in zip(_refs(papers), papers):
        ev = p.evidence
        if ev is None:
            continue
        year = p.publication_date.year if p.publication_date else "n.d."
        n = f"n={ev.sample_size}" if ev.sample_size else "n not stated"
        preprint = " | PREPRINT" if p.source in ("biorxiv", "medrxiv") else ""
        context = "; ".join(x for x in (ev.population, ev.intervention, ev.outcome) if x)
        rows.append(
            f"[{ref}] {year} | {_DESIGN_NAMES.get(ev.design, ev.design)} | {ev.organism} | {n} | "
            f"stance: {ev.stance}{preprint} | {context} | finding: {ev.key_finding}"
        )
    return "\n".join(rows)


def _facts(summary: EvidenceSummary) -> str:
    lines = [f"Papers with extracted evidence: {summary.papers_with_evidence}"]
    if summary.answerable and summary.stance_counts:
        lines.append("Stance counts: " + ", ".join(f"{v} {k}" for k, v in sorted(summary.stance_counts.items())))
        for org, counts in sorted(summary.stance_by_organism.items()):
            lines.append(f"  {org}: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))
    if summary.design_counts:
        lines.append("Study designs: " + ", ".join(
            f"{v} {_DESIGN_NAMES.get(k, k)}" for k, v in sorted(summary.design_counts.items(), key=lambda kv: -kv[1])
        ))
    if summary.largest_study:
        ls = summary.largest_study
        lines.append(f"Largest study: [{ls['ref']}] n={ls['n']} ({_DESIGN_NAMES.get(ls['design'], ls['design'])})")
    if summary.latest_rct_year:
        lines.append(f"Most recent RCT or meta-analysis: {summary.latest_rct_year}")
    if summary.preprint_count:
        lines.append(f"Preprints among them: {summary.preprint_count}")
    if summary.gaps:
        lines.append("Gaps (state these as given):")
        lines.extend(f"- {g}" for g in summary.gaps)
    return "\n".join(lines)


def grounded_prompt(query: str, summary: EvidenceSummary, papers: List[PaperResult]) -> str:
    if summary.answerable:
        task = f"""Answer the question "{summary.question}" for a researcher, in three short paragraphs:
1. Where the evidence points overall, using the counts below (do not recount), and how strong it is (designs, sizes, human vs animal).
2. Where studies disagree and the likely reasons visible in the table (population, design, organism, era, intervention).
3. What is missing or uncertain, using the gaps below."""
    else:
        task = f"""The researcher searched the topic "{summary.question}". In three short paragraphs:
1. The main themes and findings across these papers.
2. How methods or results changed over time, if the years show it.
3. What is missing or uncertain, using the gaps below."""
    return f"""You are a careful scientific research assistant. The researcher's search was: "{query}".

{task}

Facts computed from the papers (use these numbers exactly):
{_facts(summary)}

Papers ([n] | year | design | organism | sample size | stance | context | finding):
{_evidence_table(papers)}

Findings marked PREPRINT are not peer reviewed; say so when you rely on them.
{_STYLE_RULES}"""


def fallback_prompt(query: str, papers: List[PaperResult]) -> str:
    blocks = []
    for ref, p in list(zip(_refs(papers), papers))[:_FALLBACK_PAPERS]:
        year = p.publication_date.year if p.publication_date else "n.d."
        abstract = (p.abstract or "")[:_FALLBACK_ABSTRACT_CHARS]
        blocks.append(f"[{ref}] {p.title} ({year})\n{abstract}")
    papers_text = "\n\n".join(blocks)
    return f"""You are a careful scientific research assistant. Summarize what these papers say about: "{query}".
Cover key findings, where they agree or disagree, and what remains open.

Papers:
{papers_text}

{_STYLE_RULES}"""


class ResponseSynthesizer:
    """Synthesizes research results into a short, cited summary."""

    def __init__(self, gemini: Optional[GeminiClient] = None):
        self.gemini = gemini or get_gemini_client()

    async def synthesize_summary(
        self,
        papers: List[PaperResult],
        original_query: str,
        evidence_summary: Optional[EvidenceSummary] = None,
        include_ai_summary: bool = True,
    ) -> Optional[str]:
        if not include_ai_summary or not papers:
            return None
        if not self.gemini.available:
            return UNAVAILABLE

        if evidence_summary and evidence_summary.papers_with_evidence:
            prompt = grounded_prompt(original_query, evidence_summary, papers)
        else:
            prompt = fallback_prompt(original_query, papers)

        text = await self.gemini.generate_text(prompt, temperature=0.3, max_tokens=2048)
        if not text:
            return FAILED
        return sanitize_citations(text, _refs(papers))

    def format_papers_text_summary(self, papers: List[PaperResult]) -> str:
        """Plain-text list of papers (no AI)."""
        if not papers:
            return "No papers found."
        lines = [f"Found {len(papers)} relevant papers:"]
        for i, paper in enumerate(papers[:5], 1):
            year = str(paper.publication_date.year) if paper.publication_date else "Unknown"
            authors = ", ".join(paper.authors[:2]) if paper.authors else "Unknown authors"
            lines.append(f"\n{i}. {paper.title}\n   {authors} et al. ({year})\n   {paper.journal or 'Journal unknown'}")
        if len(papers) > 5:
            lines.append(f"\n... and {len(papers) - 5} more papers.")
        return "\n".join(lines)
