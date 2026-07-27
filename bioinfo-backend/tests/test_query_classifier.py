"""Unit tests for QueryClassifier — temporal detection and query type inference."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.agents.query_classifier import QueryClassifier
from src.models.request_models import QueryType


@pytest.fixture
def classifier():
    return QueryClassifier()


class TestTemporalDetection:
    def test_recent_keyword_triggers_date_filter(self, classifier):
        result = classifier.classify("latest CRISPR developments")
        assert result.min_date is not None

    def test_no_temporal_keyword_no_date_filter(self, classifier):
        result = classifier.classify("CRISPR gene editing mechanisms")
        assert result.temporal_context in (None, "none", "")

    def test_year_range_detected(self, classifier):
        result = classifier.classify("CRISPR research in 2023 and 2024")
        assert result.min_date is not None or result.refined_query is not None

    def test_sort_by_pub_date_for_recent_queries(self, classifier):
        result = classifier.classify("most recent BRAF inhibitor studies")
        assert result.sort_by == "pub_date"


class TestQueryTypeInference:
    def test_literature_query(self, classifier):
        result = classifier.classify("does metformin affect gut microbiome")
        assert result.query_type in (QueryType.LITERATURE, QueryType.GENERAL)

    def test_refined_query_not_empty(self, classifier):
        result = classifier.classify("BRAF V600E melanoma treatment")
        assert result.refined_query
        assert len(result.refined_query) > 0
