"""
Main orchestrator agent for bioinformatics research tasks.
Coordinates query classification, PubMed + preprint search, relevance scoring,
evidence extraction, and grounded response synthesis.
Supports an optional async progress_callback for WebSocket streaming.
"""
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple
import asyncio
import time

from ..models.request_models import BioinformaticsQuery
from ..models.response_models import EvidenceSummary, QueryResponse, PaperResult
from ..external.ncbi_client import NCBIClient
from ..external.icite_client import CitationInfo, ICiteClient
from ..external.preprint_client import PreprintClient, PreprintArticle
from ..services.embedding_service import EmbeddingService, get_embedding_service
from ..services.evidence_aggregator import summarize
from ..services.evidence_extractor import EvidenceExtractor, FramedQuestion, RawEvidence, build_evidence
from ..utils.embeddings import normalize_doi, normalize_title
from .query_classifier import QueryClassifier, QueryAnalysis
from .response_synthesizer import ResponseSynthesizer

ProgressCallback = Optional[Callable[[str, Optional[dict]], Coroutine[Any, Any, None]]]

PREPRINT_SERVERS = ("biorxiv", "medrxiv")
# Preprints fetched per server, at most
MAX_PREPRINTS_PER_SERVER = 10


class BioinfoAgent:
    """
    Main agent that orchestrates the research workflow:
    1. Classifies query and detects temporal requirements
    2. Searches PubMed, bioRxiv and medRxiv in parallel
    3. Merges results, dropping preprints already in PubMed
    4. Ranks by semantic similarity to the query
    5. Extracts per-paper evidence (Gemini) and citation data (iCite), then aggregates it
    6. Synthesizes a cited summary grounded in that evidence
    """

    def __init__(
        self,
        ncbi_client: NCBIClient,
        preprint_client: Optional[PreprintClient] = None,
        embedding_service: Optional[EmbeddingService] = None,
        icite_client: Optional[ICiteClient] = None,
        evidence_extractor: Optional[EvidenceExtractor] = None,
        response_synthesizer: Optional[ResponseSynthesizer] = None,
    ):
        self.ncbi_client = ncbi_client
        self.preprint_client = preprint_client or PreprintClient()
        self.embedding_service = embedding_service or get_embedding_service()
        self.icite_client = icite_client or ICiteClient()
        self.evidence_extractor = evidence_extractor or EvidenceExtractor()
        self.query_classifier = QueryClassifier()
        self.response_synthesizer = response_synthesizer or ResponseSynthesizer()

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

        # Step 2: Search PubMed and preprint servers in parallel.
        # Both events go out before the gather because both searches start now.
        await emit("searching_pubmed")
        await emit("searching_preprints")
        preprint_limit = min(query_request.max_results, MAX_PREPRINTS_PER_SERVER)
        pubmed_articles, *preprint_batches = await asyncio.gather(
            self._search_literature(
                analysis=query_analysis,
                max_results=query_request.max_results,
            ),
            *(
                self.preprint_client.search(
                    query_analysis.refined_query,
                    server=server,
                    max_results=preprint_limit,
                    min_date=query_analysis.min_date,
                    max_date=query_analysis.max_date,
                )
                for server in PREPRINT_SERVERS
            ),
        )

        # Step 3: Convert, merge and de-duplicate
        await emit("retrieving_abstracts")
        preprints = [p for batch in preprint_batches for p in batch]
        paper_results = self._soft_cap(
            self._merge_and_dedup(
                self._convert_to_paper_results(pubmed_articles),
                self._convert_preprints_to_paper_results(preprints),
            ),
            query_request.max_results,
        )

        # Step 4: Rank by semantic similarity to the query
        if paper_results:
            await emit("scoring_relevance")
            paper_results = await self.embedding_service.score_relevance(
                query_request.query, paper_results
            )

        # Fix citation numbers now: the synthesis cites [ref] and the UI shows it on each card
        paper_results = [p.model_copy(update={"ref": i}) for i, p in enumerate(paper_results, 1)]

        # Step 5: Citation data and structured evidence, in parallel
        evidence_summary: Optional[EvidenceSummary] = None
        if paper_results:
            extract = include_ai_summary and self.evidence_extractor.available
            if extract:
                await emit("extracting_evidence")
            citations, (framed, raw) = await asyncio.gather(
                self.icite_client.fetch([p.pmid for p in paper_results if p.pmid]),
                self._extract_evidence(query_request.query, paper_results) if extract else _no_evidence(),
            )
            paper_results = self._attach_evidence(paper_results, citations, raw)
            if framed is not None and raw:
                evidence_summary = summarize(paper_results, framed.question, framed.answerable)

        # Step 6: Generate AI summary
        ai_summary = None
        if include_ai_summary and paper_results:
            await emit("synthesizing")
            ai_summary = await self.response_synthesizer.synthesize_summary(
                papers=paper_results,
                original_query=query_request.query,
                evidence_summary=evidence_summary,
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
            evidence_summary=evidence_summary,
            metadata={
                "sort_by": query_analysis.sort_by,
                "temporal_context": query_analysis.temporal_context,
                "date_range": {
                    "min_date": query_analysis.min_date,
                    "max_date": query_analysis.max_date,
                } if query_analysis.min_date or query_analysis.max_date else None,
            },
        )

    async def _extract_evidence(
        self, query: str, papers: List[PaperResult]
    ) -> Tuple[Optional[FramedQuestion], Dict[int, RawEvidence]]:
        framed = await self.evidence_extractor.frame_question(query)
        if framed is None:
            return None, {}
        return framed, await self.evidence_extractor.extract(framed, papers)

    @staticmethod
    def _attach_evidence(
        papers: List[PaperResult],
        citations: Dict[str, CitationInfo],
        raw: Dict[int, RawEvidence],
    ) -> List[PaperResult]:
        out = []
        for i, paper in enumerate(papers):
            citation = citations.get(paper.pmid) if paper.pmid else None
            update: dict = {}
            if citation:
                update["citation_count"] = citation.citation_count
                update["relative_citation_ratio"] = citation.relative_citation_ratio
            if i in raw:
                update["evidence"] = build_evidence(raw[i], paper, citation)
            out.append(paper.model_copy(update=update) if update else paper)
        return out

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
                source="pubmed",
                publication_types=article.publication_types,
                mesh_terms=article.mesh_terms,
                trial_ids=article.trial_ids,
                abstract_sections=article.abstract_sections,
            )
            for article in pubmed_articles
        ]

    @staticmethod
    def _convert_preprints_to_paper_results(preprints: List[PreprintArticle]) -> List[PaperResult]:
        return [
            PaperResult(
                title=p.title,
                authors=p.authors,
                abstract=p.abstract or None,
                journal="bioRxiv" if p.server == "biorxiv" else "medRxiv",
                publication_date=p.publication_date,
                pmid=None,
                doi=p.doi or None,
                keywords=p.keywords,
                source=p.server,
            )
            for p in preprints
        ]

    @staticmethod
    def _merge_and_dedup(
        pubmed: List[PaperResult], preprints: List[PaperResult]
    ) -> List[PaperResult]:
        """
        PubMed results first, then preprints that aren't already present.
        A preprint is a duplicate if its DOI matches, or failing that its normalized title
        matches (a preprint and its published version usually have different DOIs).
        The PubMed record always wins. Preprints are also de-duplicated among themselves.
        """
        seen_dois = {normalize_doi(p.doi) for p in pubmed if p.doi}
        seen_titles = {normalize_title(p.title) for p in pubmed if p.title}

        merged = list(pubmed)
        for p in preprints:
            doi = normalize_doi(p.doi) if p.doi else ""
            title = normalize_title(p.title)
            if (doi and doi in seen_dois) or (title and title in seen_titles):
                continue
            merged.append(p)
            if doi:
                seen_dois.add(doi)
            if title:
                seen_titles.add(title)
        return merged

    @staticmethod
    def _soft_cap(papers: List[PaperResult], max_results: int) -> List[PaperResult]:
        """Allow preprints to add up to 50% on top of the requested PubMed count."""
        return papers[:int(max_results * 1.5)]

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


async def _no_evidence() -> Tuple[None, Dict[int, RawEvidence]]:
    return None, {}
