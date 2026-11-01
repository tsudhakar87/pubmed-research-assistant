"""
Main orchestrator agent for bioinformatics research tasks.
Coordinates query classification, literature search, and response synthesis.
Supports an optional async progress_callback for WebSocket streaming.
"""
from typing import Any, Callable, Coroutine, List, Optional
import time

from ..models.request_models import BioinformaticsQuery
from ..models.response_models import QueryResponse, PaperResult
from ..external.ncbi_client import NCBIClient
from .query_classifier import QueryClassifier, QueryAnalysis
from .response_synthesizer import ResponseSynthesizer

ProgressCallback = Optional[Callable[[str, Optional[dict]], Coroutine[Any, Any, None]]]


class BioinfoAgent:
    """
    Main agent that orchestrates the research workflow:
    1. Classifies query and detects temporal requirements
    2. Searches PubMed with optimised parameters
    3. Synthesizes results with AI-generated summaries
    """

    def __init__(self, ncbi_client: NCBIClient):
        self.ncbi_client = ncbi_client
        self.query_classifier = QueryClassifier()
        self.response_synthesizer = ResponseSynthesizer()

    async def process_query(
        self,
        query_request: BioinformaticsQuery,
        query_id: str,
        include_ai_summary: bool = True,
        progress_callback: ProgressCallback = None,
    ) -> QueryResponse:
        """
        Process a research query end-to-end.

        Args:
            query_request: User's query request
            query_id: Unique query identifier
            include_ai_summary: Whether to generate AI summary
            progress_callback: Optional async callable(event, data) for streaming progress

        Returns:
            QueryResponse with results and metadata
        """
        start_time = time.time()

        async def emit(event: str, data: Optional[dict] = None) -> None:
            if progress_callback:
                await progress_callback(event, data)

        # Step 1: Classify query
        await emit("classifying")
        query_analysis = self.query_classifier.classify(
            query=query_request.query,
            query_type=query_request.query_type,
        )

        # Step 2: Search PubMed
        await emit("searching_pubmed")
        pubmed_articles = await self._search_literature(
            analysis=query_analysis,
            max_results=query_request.max_results,
        )

        # Step 3: Retrieve / convert articles
        await emit("retrieving_abstracts")
        paper_results = self._convert_to_paper_results(pubmed_articles)

        # Step 4: Generate AI summary
        ai_summary = None
        if include_ai_summary and paper_results:
            await emit("synthesizing")
            ai_summary = await self.response_synthesizer.synthesize_summary(
                papers=paper_results,
                original_query=query_request.query,
            )

        processing_time = int((time.time() - start_time) * 1000)

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
                    "max_date": query_analysis.max_date,
                } if query_analysis.min_date or query_analysis.max_date else None,
            },
        )

    async def _search_literature(self, analysis: QueryAnalysis, max_results: int) -> List:
        search_kwargs = {"sort": analysis.sort_by}
        if analysis.min_date:
            search_kwargs["min_date"] = analysis.min_date
        if analysis.max_date:
            search_kwargs["max_date"] = analysis.max_date

        return await self.ncbi_client.search_and_fetch(
            query=analysis.refined_query,
            max_results=max_results,
            **search_kwargs,
        )

    def _convert_to_paper_results(self, pubmed_articles: List) -> List[PaperResult]:
        return [
            PaperResult(
                title=article.title,
                authors=article.authors,
                abstract=article.abstract,
                journal=article.journal,
                publication_date=article.publication_date,
                pmid=article.pmid,
                doi=article.doi,
                keywords=article.keywords,
                relevance_score=None,
            )
            for article in pubmed_articles
        ]

    async def get_latest_papers(
        self, topic: str, max_results: int = 10, years_back: int = 2
    ) -> List[PaperResult]:
        from datetime import datetime, timedelta
        min_date = (datetime.now() - timedelta(days=365 * years_back)).strftime("%Y/%m/%d")
        articles = await self.ncbi_client.search_and_fetch(
            query=topic,
            max_results=max_results,
            sort="pub_date",
            min_date=min_date,
        )
        return self._convert_to_paper_results(articles)
