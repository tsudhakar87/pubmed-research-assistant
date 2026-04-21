"""
Query classifier agent that analyzes user queries to determine:
- Query type (literature, sequence, general)
- Temporal requirements (recent, last N years, date range)
- Search strategy (sort order, filters)
"""
from typing import Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import re

from ..models.request_models import QueryType


@dataclass
class QueryAnalysis:
    """Result of query classification"""
    query_type: QueryType
    refined_query: str
    sort_by: str  # "pub_date" or "relevance"
    min_date: Optional[str] = None  # YYYY/MM/DD format
    max_date: Optional[str] = None  # YYYY/MM/DD format
    temporal_context: Optional[str] = None  # "recent", "last_year", "last_5_years", etc.


class QueryClassifier:
    """Classifies and analyzes user queries for optimal search strategy"""

    # Temporal keywords indicating recency
    RECENT_KEYWORDS = {
        "latest", "recent", "new", "current", "newest",
        "up-to-date", "contemporary", "modern", "emerging"
    }

    # Year-based patterns
    YEAR_PATTERNS = [
        (r"(?:in |from |since )(\d{4})", "since_year"),
        (r"(?:last |past )(\d+)\s*years?", "last_n_years"),
        (r"(\d{4})\s*to\s*(\d{4})", "year_range"),
    ]

    # Query type indicators
    SEQUENCE_KEYWORDS = {"sequence", "protein", "genome", "dna", "rna", "amino acid", "nucleotide"}

    def classify(self, query: str, query_type: Optional[QueryType] = None) -> QueryAnalysis:
        """
        Classify and analyze a user query

        Args:
            query: User's research question
            query_type: Optional pre-specified query type

        Returns:
            QueryAnalysis with search parameters
        """
        query_lower = query.lower()

        # Auto-detect query type if not provided
        if query_type is None:
            query_type = self._detect_query_type(query_lower)

        # Analyze temporal requirements
        temporal_info = self._analyze_temporal_requirements(query, query_lower)

        # Refine the query (remove temporal keywords for cleaner search)
        refined_query = self._refine_query(query, temporal_info)

        return QueryAnalysis(
            query_type=query_type,
            refined_query=refined_query,
            sort_by=temporal_info["sort_by"],
            min_date=temporal_info.get("min_date"),
            max_date=temporal_info.get("max_date"),
            temporal_context=temporal_info.get("context")
        )

    def _detect_query_type(self, query_lower: str) -> QueryType:
        """Detect the type of query based on keywords"""
        # Check for sequence-related queries
        if any(keyword in query_lower for keyword in self.SEQUENCE_KEYWORDS):
            return QueryType.SEQUENCE

        # Check for literature-related queries
        literature_indicators = {
            "research", "study", "studies", "findings", "papers",
            "articles", "publications", "literature", "reviews"
        }
        if any(keyword in query_lower for keyword in literature_indicators):
            return QueryType.LITERATURE

        # Default to general
        return QueryType.GENERAL

    def _analyze_temporal_requirements(self, query: str, query_lower: str) -> dict:
        """
        Analyze temporal requirements in the query

        Returns:
            Dict with sort_by, min_date, max_date, and context
        """
        today = datetime.now()
        result = {
            "sort_by": "relevance",  # Default
            "context": None
        }

        # Check for recent/latest keywords
        if any(keyword in query_lower for keyword in self.RECENT_KEYWORDS):
            # User wants recent articles - last 2 years, sorted by date
            min_date = today - timedelta(days=365*2)
            result.update({
                "sort_by": "pub_date",
                "min_date": min_date.strftime("%Y/%m/%d"),
                "context": "recent"
            })
            return result

        # Check for year-based patterns
        for pattern, pattern_type in self.YEAR_PATTERNS:
            match = re.search(pattern, query_lower)
            if match:
                if pattern_type == "since_year":
                    year = int(match.group(1))
                    result.update({
                        "sort_by": "pub_date",
                        "min_date": f"{year}/01/01",
                        "context": f"since_{year}"
                    })
                    return result

                elif pattern_type == "last_n_years":
                    n_years = int(match.group(1))
                    min_date = today - timedelta(days=365*n_years)
                    result.update({
                        "sort_by": "pub_date",
                        "min_date": min_date.strftime("%Y/%m/%d"),
                        "context": f"last_{n_years}_years"
                    })
                    return result

                elif pattern_type == "year_range":
                    start_year = int(match.group(1))
                    end_year = int(match.group(2))
                    result.update({
                        "sort_by": "pub_date",
                        "min_date": f"{start_year}/01/01",
                        "max_date": f"{end_year}/12/31",
                        "context": f"{start_year}_to_{end_year}"
                    })
                    return result

        # No temporal requirements found - use relevance sorting
        return result

    def _refine_query(self, query: str, temporal_info: dict) -> str:
        """
        Refine the query by removing temporal keywords for cleaner PubMed search

        Args:
            query: Original query
            temporal_info: Temporal analysis results

        Returns:
            Refined query string
        """
        refined = query

        # Remove common temporal keywords that don't help PubMed search
        temporal_phrases = [
            r"\b(?:what are the |what is the |show me |find )?(?:latest|recent|new|newest|current|up-to-date)\s+",
            r"\b(?:in |from |since )\d{4}\b",
            r"\b(?:last |past )\d+\s*years?\b",
            r"\b\d{4}\s*to\s*\d{4}\b",
            r"\bresearch findings? on\s+",
            r"\bstudies (?:on|about)\s+",
            r"\barticles (?:on|about)\s+",
        ]

        for pattern in temporal_phrases:
            refined = re.sub(pattern, "", refined, flags=re.IGNORECASE)

        # Clean up extra whitespace
        refined = re.sub(r'\s+', ' ', refined).strip()

        # If the refined query is too short, return original
        if len(refined) < 3:
            return query

        return refined
