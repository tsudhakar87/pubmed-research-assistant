"""
Deterministic aggregation of per-paper Evidence into an EvidenceSummary.

Every number the user sees, and every "gap" sentence the synthesis may repeat,
is computed here from the extracted fields. The LLM never counts.
"""
from collections import Counter
from datetime import datetime
from statistics import median
from typing import Dict, List, Optional

from ..models.response_models import EvidenceSummary, PaperResult

DIRECTIONAL = ("supports", "contradicts", "mixed", "no_effect")
STANCES = DIRECTIONAL + ("not_applicable",)
HIGH_LEVEL_DESIGNS = {"meta_analysis", "systematic_review", "rct"}
# Below this many papers with evidence, gap statements are more noise than signal
MIN_PAPERS_FOR_GAPS = 3
SMALL_STUDY_N = 50
STALE_RCT_YEARS = 5

_STANCE_WORDS = {
    "supports": "supportive",
    "contradicts": "contradicting",
    "mixed": "mixed",
    "no_effect": "no effect",
}


def _majority(stances: List[str]) -> Optional[str]:
    """Most common directional stance, if it is a strict plurality and there are >= 2 studies."""
    directional = [s for s in stances if s in DIRECTIONAL]
    if len(directional) < 2:
        return None
    (top, n), *rest = Counter(directional).most_common() + [(None, 0)]
    return top if n > rest[0][1] else None


def summarize(
    papers: List[PaperResult],
    question: str,
    answerable: bool,
    now: Optional[datetime] = None,
) -> EvidenceSummary:
    now = now or datetime.now()
    with_ev = [p for p in papers if p.evidence is not None]

    stance_counts = Counter(p.evidence.stance for p in with_ev)
    design_counts = Counter(p.evidence.design for p in with_ev)

    by_organism: Dict[str, Counter] = {}
    for p in with_ev:
        by_organism.setdefault(p.evidence.organism, Counter())[p.evidence.stance] += 1

    years: Dict[int, Counter] = {}
    for p in with_ev:
        if p.publication_date:
            years.setdefault(p.publication_date.year, Counter())[p.evidence.stance] += 1
    by_year = [
        {"year": y, **{s: c.get(s, 0) for s in STANCES}, "total": sum(c.values())}
        for y, c in sorted(years.items())
    ]

    sized = [p for p in with_ev if p.evidence.sample_size]
    largest = max(sized, key=lambda p: p.evidence.sample_size, default=None)

    rct_years = [p.publication_date.year for p in with_ev
                 if p.evidence.design in ("rct", "meta_analysis") and p.publication_date]
    latest_rct_year = max(rct_years, default=None)

    summary = EvidenceSummary(
        question=question,
        answerable=answerable,
        papers_with_evidence=len(with_ev),
        stance_counts=dict(stance_counts),
        stance_by_organism={org: dict(c) for org, c in by_organism.items()},
        design_counts=dict(design_counts),
        by_year=by_year,
        largest_study=(
            {"ref": largest.ref, "n": largest.evidence.sample_size, "design": largest.evidence.design}
            if largest else None
        ),
        latest_rct_year=latest_rct_year,
        preprint_count=sum(1 for p in with_ev if p.source in ("biorxiv", "medrxiv")),
    )
    summary.gaps = find_gaps(with_ev, summary, now)
    return summary


def find_gaps(with_ev: List[PaperResult], summary: EvidenceSummary, now: datetime) -> List[str]:
    if len(with_ev) < MIN_PAPERS_FOR_GAPS:
        return []
    gaps: List[str] = []

    if not any(p.evidence.design in HIGH_LEVEL_DESIGNS for p in with_ev):
        gaps.append("No randomized trials or meta-analyses among these results.")
    elif summary.latest_rct_year and summary.latest_rct_year <= now.year - STALE_RCT_YEARS:
        gaps.append(f"The most recent randomized trial or meta-analysis here is from {summary.latest_rct_year}.")

    human = [p for p in with_ev if p.evidence.organism in ("human", "mixed")]
    if not human:
        gaps.append("No human studies among these results.")
    else:
        sizes = [p.evidence.sample_size for p in human if p.evidence.sample_size]
        if sizes and len(sizes) == len(human) and max(sizes) < SMALL_STUDY_N:
            gaps.append(f"Human evidence comes only from small studies (largest n = {max(sizes)}).")

    if not summary.answerable:
        return gaps

    human_major = _majority([p.evidence.stance for p in with_ev if p.evidence.organism == "human"])
    animal_major = _majority([p.evidence.stance for p in with_ev if p.evidence.organism == "animal"])
    if human_major and animal_major and human_major != animal_major:
        gaps.append(
            "Human and animal studies point in different directions: human studies are mostly "
            f"{_STANCE_WORDS[human_major]}, animal studies mostly {_STANCE_WORDS[animal_major]}."
        )

    dated = sorted((p for p in with_ev if p.publication_date), key=lambda p: p.publication_date)
    if len(dated) >= 4:
        split_year = int(median(p.publication_date.year for p in dated))
        early = _majority([p.evidence.stance for p in dated if p.publication_date.year < split_year])
        late = _majority([p.evidence.stance for p in dated if p.publication_date.year >= split_year])
        if early and late and early != late:
            gaps.append(
                f"Findings shifted over time: mostly {_STANCE_WORDS[early]} before {split_year}, "
                f"mostly {_STANCE_WORDS[late]} from {split_year} on."
            )

    supporting = [p for p in with_ev if p.evidence.stance == "supports"]
    preprint_support = sum(1 for p in supporting if p.source in ("biorxiv", "medrxiv"))
    if len(supporting) >= 2 and preprint_support * 2 > len(supporting):
        gaps.append("Most of the supporting evidence comes from preprints that are not yet peer reviewed.")

    return gaps
