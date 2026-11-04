"""Tests for parse_pubmed_xml against a hand-written EFetch-format fixture."""
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.external.data_parser import NO_ABSTRACT, parse_pubmed_xml

FIXTURE = Path(__file__).parent / "fixtures" / "pubmed_efetch_sample.xml"


@pytest.fixture(scope="module")
def articles():
    return {a.pmid: a for a in parse_pubmed_xml(FIXTURE.read_text())}


class TestInlineMarkup:
    def test_title_keeps_text_after_italics(self, articles):
        assert articles["39000001"].title == (
            "Metformin and Akkermansia muciniphila abundance: a randomized trial"
        )

    def test_abstract_keeps_text_after_inline_tags(self, articles):
        a = articles["39000001"]
        assert "A. muciniphila relative abundance by 2.1-fold" in a.abstract
        assert "CO2 output unchanged" in articles["39000002"].abstract


class TestStructuredAbstract:
    def test_sections_by_label(self, articles):
        sections = articles["39000001"].abstract_sections
        assert list(sections) == ["BACKGROUND", "METHODS", "RESULTS", "CONCLUSIONS"]
        assert sections["METHODS"].startswith("We randomized 240 adults")

    def test_unstructured_has_no_sections(self, articles):
        assert articles["39000002"].abstract_sections == {}

    def test_joined_abstract_still_present(self, articles):
        a = articles["39000001"].abstract
        assert a.startswith("Metformin may act partly") and a.endswith("composition in humans.")


class TestMetadata:
    def test_publication_types(self, articles):
        assert articles["39000001"].publication_types == ["Journal Article", "Randomized Controlled Trial"]

    def test_mesh_terms(self, articles):
        assert articles["39000001"].mesh_terms == ["Humans", "Metformin", "Gastrointestinal Microbiome"]
        assert "Mice" in articles["39000002"].mesh_terms

    def test_trial_ids(self, articles):
        assert articles["39000001"].trial_ids == ["NCT04123456"]
        assert articles["39000002"].trial_ids == []

    def test_existing_fields_unchanged(self, articles):
        a = articles["39000001"]
        assert a.doi == "10.2337/dc23-0001"
        assert a.journal == "Diabetes Care"
        assert a.authors == ["Ana Rivera", "Chidi Okafor"]
        assert a.publication_date == datetime(2024, 3, 5)
        assert a.keywords == ["microbiome"]


class TestMissingAbstract:
    def test_flag_and_placeholder(self, articles):
        a = articles["39000003"]
        assert a.has_abstract is False
        assert a.abstract == NO_ABSTRACT
        assert a.mesh_terms == []

    def test_present_abstract_flag(self, articles):
        assert articles["39000001"].has_abstract is True
