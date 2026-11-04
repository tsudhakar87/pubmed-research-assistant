"""
Checks against real API responses saved by scripts/phase0_check.py
("metformin gut microbiome", 20 results). These confirm the parsers and
labeling rules work on actual PubMed and iCite output, not just the
hand-written fixtures.
"""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.external.data_parser import parse_pubmed_xml
from src.external.icite_client import parse_record
from src.utils.study_design import design_from_pubtypes, organism_from_mesh

REAL = Path(__file__).parent / "fixtures" / "real"


@pytest.fixture(scope="module")
def articles():
    return {a.pmid: a for a in parse_pubmed_xml((REAL / "pubmed_efetch.xml").read_text())}


@pytest.fixture(scope="module")
def icite():
    data = json.loads((REAL / "icite_pubs.json").read_text())["data"]
    return {c.pmid: c for c in map(parse_record, data)}


def test_all_records_parse_with_abstracts(articles):
    assert len(articles) == 20
    assert all(a.has_abstract and a.title for a in articles.values())


def test_structured_abstract_and_trial_id(articles):
    rct = articles["34006565"]  # 2021 RCT, registered NCT02431676
    assert rct.trial_ids == ["NCT02431676"]
    assert len(rct.abstract_sections) == 4
    assert design_from_pubtypes(rct.publication_types) == "rct"
    assert organism_from_mesh(rct.mesh_terms, "rct") == "human"


def test_review_labels(articles):
    review = articles["32409589"]
    assert design_from_pubtypes(review.publication_types) == "review"


def test_unindexed_record_falls_through(articles):
    # Broiler-hen study not yet MeSH-indexed: metadata can't label the organism
    hens = articles["36203937"]
    assert hens.mesh_terms == []
    assert organism_from_mesh(hens.mesh_terms) is None


def test_animal_from_mesh(articles):
    assert organism_from_mesh(articles["35191819"].mesh_terms) == "animal"


def test_icite_covers_every_pmid(articles, icite):
    assert set(icite) == set(articles)
    assert all(c.citation_count >= 0 for c in icite.values())
    assert icite["26633628"].citation_count > 1000
    assert icite["26633628"].relative_citation_ratio > 10


def test_real_reviews_never_count_toward_stance(articles):
    # Phase 0: Gemini said "supports" for these three narrative reviews
    from src.models.response_models import PaperResult
    from src.services.evidence_extractor import PaperExtraction, RawEvidence, build_evidence

    for pmid in ("30874963", "37603460", "33808194"):
        a = articles[pmid]
        paper = PaperResult(title=a.title, authors=a.authors, abstract=a.abstract, pmid=a.pmid,
                            publication_types=a.publication_types, mesh_terms=a.mesh_terms)
        item = PaperExtraction(index=1, design="review", organism="human", sample_size=None,
                               population=None, intervention=None, outcome=None, stance="supports",
                               key_finding="x", finding_quote="x")
        assert build_evidence(RawEvidence(extraction=item, quote=None), paper).stance == "not_applicable"
