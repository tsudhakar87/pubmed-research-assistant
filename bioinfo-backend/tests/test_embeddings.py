"""Unit tests for the pure helpers in src/utils/embeddings.py."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.embeddings import cosine_similarity, normalize_doi, normalize_title


class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        assert cosine_similarity([1, 2], [-1, -2]) == pytest.approx(-1.0)

    def test_scale_invariant(self):
        assert cosine_similarity([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0)

    def test_empty_vector(self):
        assert cosine_similarity([], [1, 0]) == 0.0

    def test_length_mismatch(self):
        assert cosine_similarity([1, 0], [1, 0, 0]) == 0.0

    def test_zero_vector(self):
        assert cosine_similarity([0, 0], [1, 0]) == 0.0


class TestNormalizeTitle:
    def test_strips_punctuation_and_case(self):
        assert normalize_title("CRISPR-Cas9 Editing!") == "crisprcas9 editing"

    def test_collapses_whitespace(self):
        assert normalize_title("  Gene   editing\n in mice ") == "gene editing in mice"

    def test_trailing_period_ignored(self):
        assert normalize_title("A study of X.") == normalize_title("A Study of X")

    def test_none_safe(self):
        assert normalize_title(None) == ""


class TestNormalizeDoi:
    def test_case_insensitive(self):
        assert normalize_doi("10.1101/2024.01.01.ABC") == "10.1101/2024.01.01.abc"

    def test_strips_resolver_prefix(self):
        assert normalize_doi("https://doi.org/10.1038/X") == "10.1038/x"

    def test_strips_doi_scheme(self):
        assert normalize_doi("doi:10.1038/x") == "10.1038/x"
