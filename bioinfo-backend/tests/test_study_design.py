"""Tests for design/organism rules from PubMed metadata."""
import os
import sys
from typing import get_args

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.study_design import (
    DESIGN_TIER,
    StudyDesign,
    design_for_organism,
    design_from_pubtypes,
    organism_from_icite,
    organism_from_mesh,
)


class TestDesignFromPubtypes:
    @pytest.mark.parametrize("pubtypes,expected", [
        (["Journal Article", "Randomized Controlled Trial"], "rct"),
        (["Review", "Meta-Analysis"], "meta_analysis"),
        (["Systematic Review", "Review"], "systematic_review"),
        (["Clinical Trial, Phase III", "Journal Article"], "clinical_trial"),
        (["Observational Study"], "observational"),
        (["Case Reports"], "case_report"),
        (["Review"], "review"),
        (["Journal Article"], None),
        ([], None),
    ])
    def test_mapping(self, pubtypes, expected):
        assert design_from_pubtypes(pubtypes) == expected

    def test_protocol_is_not_a_trial(self):
        assert design_from_pubtypes(["Clinical Trial Protocol"]) == "other"

    def test_erratum_is_other(self):
        assert design_from_pubtypes(["Journal Article", "Published Erratum"]) == "other"

    def test_comment_on_rct_keeps_rct(self):
        assert design_from_pubtypes(["Comment", "Randomized Controlled Trial"]) == "rct"

    def test_every_design_has_a_tier(self):
        assert set(get_args(StudyDesign)) == set(DESIGN_TIER)


class TestOrganismFromMesh:
    def test_humans(self):
        assert organism_from_mesh(["Humans", "Metformin"]) == "human"

    def test_animals(self):
        assert organism_from_mesh(["Animals", "Mice"]) == "animal"

    def test_species_without_check_tag(self):
        assert organism_from_mesh(["Zebrafish"]) == "animal"

    def test_both_is_mixed(self):
        assert organism_from_mesh(["Humans", "Animals", "Mice"]) == "mixed"

    def test_human_cell_line_is_in_vitro(self):
        assert organism_from_mesh(["Humans", "Cell Line, Tumor"]) == "in_vitro"

    def test_cells_in_clinical_study_stay_human(self):
        assert organism_from_mesh(["Humans", "Cells, Cultured"], design="rct") == "human"

    def test_untagged(self):
        assert organism_from_mesh([]) is None
        assert organism_from_mesh(["Metformin"]) is None


class TestOrganismFromIcite:
    def test_dominant_human(self):
        assert organism_from_icite(0.9, 0.1, 0.0) == "human"

    def test_dominant_molecular(self):
        assert organism_from_icite(0.0, 0.25, 0.75) == "in_vitro"

    def test_no_clear_winner(self):
        assert organism_from_icite(0.5, 0.5, 0.0) is None

    def test_missing_values(self):
        assert organism_from_icite(None, None, None) is None


def test_design_for_organism():
    assert design_for_organism("animal") == "animal"
    assert design_for_organism("in_vitro") == "in_vitro"
    assert design_for_organism("human") is None
    assert design_for_organism(None) is None
