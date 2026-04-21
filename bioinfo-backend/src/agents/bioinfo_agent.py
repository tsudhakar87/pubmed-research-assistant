"""
Main orchestrator agent for bioinformatics research tasks
Coordinates query classification, literature search, and response synthesis
"""
from typing import List, Optional
import time

from ..models.request_models import BioinformaticsQuery, QueryType
from ..models.response_models import QueryResponse, PaperResult
from ..external.ncbi_client import NCBIClient
from .query_classifier import QueryClassifier, QueryAnalysis
from .response_synthesizer import ResponseSynthesizer


class BioinfoAgent:
    """
    Main agent that orchestrates the research workflow:
    1. Classifies query and detects temporal requirements
    2. Searches PubMed with optimized parameters
    3. Synthesizes results with AI-generated summaries
    """

    def __init__(self, ncbi_client: NCBIClient):
        """
        Initialize the bioinfo agent

        Args:
            ncbi_client: Initialized NCBI client instance
        """
        self.ncbi_client = ncbi_client
        self.query_classifier = QueryClassifier()
        self.response_synthesizer = ResponseSynthesizer()

    async def process_query(
        self,
        query_request: BioinformaticsQuery,
        query_id: str,
        include_ai_summary: bool = True
    ) -> QueryResponse:
        """
        Process a research query end-to-end

        Args:
            query_request: User's query request
            query_id: Unique query identifier
            include_ai_summary: Whether to generate AI summary

        Returns:
            QueryResponse with results and metadata
        """
        start_time = time.time()

        # Step 1: Classify query and analyze temporal requirements
        query_analysis = self.query_classifier.classify(
            query=query_request.query,
            query_type=query_request.query_type
        )

        # Step 2: Search PubMed with optimized parameters
        pubmed_articles = await self._search_literature(
            analysis=query_analysis,
            max_results=query_request.max_results
        )

        # Step 3: Convert to PaperResult objects
        paper_results = self._convert_to_paper_results(pubmed_articles)

        # Step 4: Generate AI summary if enabled
        ai_summary = None
        if include_ai_summary and paper_results:
            ai_summary = await self.response_synthesizer.synthesize_summary(
                papers=paper_results,
                original_query=query_request.query
            )

        processing_time = int((time.time() - start_time) * 1000)

        # Build response
        return QueryResponse(
            query_id=query_id,
            original_query=query_request.query,
            refined_query=query_analysis.refined_query,
            query_type=query_analysis.query_type,
            literature_results=paper_results,
            total_results=len(paper_results),
            processing_time=processing_time,
            ai_summary=ai_summary,
            metadata={
                "sort_by": query_analysis.sort_by,
                "temporal_context": query_analysis.temporal_context,
                "date_range": {
                    "min_date": query_analysis.min_date,
                    "max_date": query_analysis.max_date
                } if query_analysis.min_date or query_analysis.max_date else None
            }
        )

    async def _search_literature(
        self,
        analysis: QueryAnalysis,
        max_results: int
    ) -> List:
        """
        Search literature using classified query parameters

        Args:
            analysis: Query analysis from classifier
            max_results: Maximum number of results

        Returns:
            List of PubMedArticle objects
        """
        search_kwargs = {
            "sort": analysis.sort_by,
        }

        # Add date filters if present
        if analysis.min_date:
            search_kwargs["min_date"] = analysis.min_date
        if analysis.max_date:
            search_kwargs["max_date"] = analysis.max_date

        # Use refined query for better search results
        search_query = analysis.refined_query

        # Search and fetch articles
        pubmed_articles = await self.ncbi_client.search_and_fetch(
            query=search_query,
            max_results=max_results,
            **search_kwargs
        )

        return pubmed_articles

    def _convert_to_paper_results(self, pubmed_articles: List) -> List[PaperResult]:
        """
        Convert PubMedArticle objects to PaperResult objects

        Args:
            pubmed_articles: List of PubMedArticle objects

        Returns:
            List of PaperResult objects
        """
        paper_results = [
            PaperResult(
                title=article.title,
                authors=article.authors,
                abstract=article.abstract,
                journal=article.journal,
                publication_date=article.publication_date,
                pmid=article.pmid,
                doi=article.doi,
                keywords=article.keywords,
                relevance_score=None
            )
            for article in pubmed_articles
        ]

        return paper_results

    async def get_latest_papers(
        self,
        topic: str,
        max_results: int = 10,
        years_back: int = 2
    ) -> List[PaperResult]:
        """
        Convenience method to get latest papers on a topic

        Args:
            topic: Research topic
            max_results: Maximum number of results
            years_back: How many years back to search

        Returns:
            List of recent PaperResult objects
        """
        from datetime import datetime, timedelta

        min_date = (datetime.now() - timedelta(days=365*years_back)).strftime("%Y/%m/%d")

        pubmed_articles = await self.ncbi_client.search_and_fetch(
            query=topic,
            max_results=max_results,
            sort="pub_date",
            min_date=min_date
        )

        return self._convert_to_paper_results(pubmed_articles)
