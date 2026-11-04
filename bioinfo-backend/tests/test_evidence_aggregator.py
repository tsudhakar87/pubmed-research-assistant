"""Tests for the deterministic evidence aggregation and gap rules."""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models.response_models import Evidence, PaperResult
from src.services.evidence_aggregator import summarize

NOW = datetime(2026, 11, 4)


def _p(ref, year, stance="supports", design="cohort", organism="human", n=None, source="pubmed", evidence=True):
    ev = Evidence(design=design, design_source="ai", organism=organism, organism_source="ai",
                  sample_size=n, stance=stance, key_finding="x") if evidence else None
    return PaperResult(title=f"P{ref}", authors=[], ref=ref, source=source,
                       publication_date=datetime(year, 6, 1), evidence=ev)


def _summary(papers, answerable=True):
    return summarize(papers, "Does X affect Y?", answerable, now=NOW)


class TestCounts:
    def test_stance_design_and_organism_counts(self):
        s = _summary([
            _p(1, 2024, "supports", "rct", "human", 300),
            _p(2, 2023, "contradicts", "animal", "animal", 20),
            _p(3, 2023, "supports", "animal", "animal"),
            _p(4, 2022, evidence=False),
        ])
        assert s.papers_with_evidence == 3
        assert s.stance_counts == {"supports": 2, "contradicts": 1}
        assert s.design_counts == {"rct": 1, "animal": 2}
        assert s.stance_by_organism == {"human": {"supports": 1}, "animal": {"contradicts": 1, "supports": 1}}

    def test_by_year_sorted_with_all_stances(self):
        s = _summary([_p(1, 2024), _p(2, 2021, "no_effect"), _p(3, 2024, "mixed")])
        assert [row["year"] for row in s.by_year] == [2021, 2024]
        assert s.by_year[1] == {"year": 2024, "supports": 1, "contradicts": 0, "mixed": 1,
                                "no_effect": 0, "not_applicable": 0, "total": 2}

    def test_largest_study_and_latest_rct(self):
        s = _summary([_p(1, 2019, design="rct", n=80), _p(2, 2022, design="meta_analysis"), _p(3, 2024, n=1200)])
        assert s.largest_study == {"ref": 3, "n": 1200, "design": "cohort"}
        assert s.latest_rct_year == 2022

    def test_preprint_count(self):
        s = _summary([_p(1, 2025, source="biorxiv"), _p(2, 2025, source="medrxiv"), _p(3, 2025)])
        assert s.preprint_count == 2

    def test_empty(self):
        s = _summary([])
        assert s.papers_with_evidence == 0 and s.gaps == [] and s.largest_study is None


class TestGaps:
    def test_too_few_papers_no_gaps(self):
        assert _summary([_p(1, 2024), _p(2, 2024)]).gaps == []

    def test_no_trials(self):
        gaps = _summary([_p(1, 2024, n=500), _p(2, 2023, n=400), _p(3, 2022, n=300)]).gaps
        assert "No randomized trials or meta-analyses among these results." in gaps

    def test_stale_trial(self):
        gaps = _summary([_p(1, 2018, design="rct", n=100), _p(2, 2024, n=90), _p(3, 2025, n=70)]).gaps
        assert "The most recent randomized trial or meta-analysis here is from 2018." in gaps

    def test_recent_trial_no_gap(self):
        gaps = _summary([_p(1, 2025, design="rct", n=100), _p(2, 2024, n=90), _p(3, 2025, n=70)]).gaps
        assert not any("randomized" in g for g in gaps)

    def test_no_human_studies(self):
        gaps = _summary([_p(i, 2024, design="animal", organism="animal") for i in range(3)]).gaps
        assert "No human studies among these results." in gaps

    def test_only_small_human_studies(self):
        gaps = _summary([_p(1, 2024, n=30), _p(2, 2024, n=12), _p(3, 2024, design="animal", organism="animal")]).gaps
        assert "Human evidence comes only from small studies (largest n = 30)." in gaps

    def test_small_study_gap_needs_all_sizes_known(self):
        gaps = _summary([_p(1, 2024, n=30), _p(2, 2024), _p(3, 2024, n=20)]).gaps
        assert not any("small studies" in g for g in gaps)

    def test_human_vs_animal_disagree(self):
        papers = [_p(1, 2024, "supports", n=100), _p(2, 2024, "supports", n=200),
                  _p(3, 2024, "no_effect", "animal", "animal"), _p(4, 2024, "no_effect", "animal", "animal")]
        gaps = _summary(papers).gaps
        assert ("Human and animal studies point in different directions: human studies are mostly "
                "supportive, animal studies mostly no effect.") in gaps

    def test_shift_over_time(self):
        papers = [_p(1, 2015, "supports", n=100), _p(2, 2016, "supports", n=100),
                  _p(3, 2023, "contradicts", n=100), _p(4, 2024, "contradicts", n=100)]
        gaps = _summary(papers).gaps
        assert any(g.startswith("Findings shifted over time: mostly supportive before 2019") for g in gaps)

    def test_tie_is_not_a_majority(self):
        papers = [_p(1, 2015, "supports", n=100), _p(2, 2016, "contradicts", n=100),
                  _p(3, 2023, "contradicts", n=100), _p(4, 2024, "contradicts", n=100)]
        assert not any("shifted" in g for g in _summary(papers).gaps)

    def test_preprint_heavy_support(self):
        papers = [_p(1, 2025, source="biorxiv", n=100), _p(2, 2025, source="medrxiv", n=100), _p(3, 2025, n=100)]
        assert any("preprints" in g for g in _summary(papers).gaps)

    def test_topic_query_skips_stance_gaps(self):
        papers = [_p(1, 2015, "supports", n=100), _p(2, 2016, "supports", n=100),
                  _p(3, 2023, "contradicts", n=100), _p(4, 2024, "contradicts", n=100)]
        gaps = _summary(papers, answerable=False).gaps
        assert not any("shifted" in g for g in gaps)
        assert "No randomized trials or meta-analyses among these results." in gaps
