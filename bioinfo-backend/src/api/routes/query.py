from fastapi import APIRouter, HTTPException, Depends
import uuid
import time
from typing import Optional

from ...models.request_models import BioinformaticsQuery
from ...models.response_models import QueryResponse, PaperResult
from ...config.settings import settings
from ....external.ncbi_client import NCBIClient

router = APIRouter(prefix="/query", tags=["Research"])

# NCBI client singleton
_ncbi_client: Optional[NCBIClient] = None


async def get_ncbi_client() -> NCBIClient:
    """Dependency to get NCBI client instance"""
    global _ncbi_client
    if _ncbi_client is None:
        _ncbi_client = NCBIClient(
            email=settings.ncbi_email,
            api_key=settings.ncbi_api_key,
            tool_name=settings.ncbi_tool_name
        )
    return _ncbi_client

@router.post("/research", response_model=QueryResponse)
async def research_query(
    query_request: BioinformaticsQuery,
    ncbi_client: NCBIClient = Depends(get_ncbi_client)
) -> QueryResponse:
    """Submit a research query and fetch results from PubMed"""
    start_time = time.time()
    query_id = f"q_{uuid.uuid4().hex[:8]}"

    try:
        # Search and fetch articles from NCBI PubMed
        pubmed_articles = await ncbi_client.search_and_fetch(
            query=query_request.query,
            max_results=query_request.max_results
        )

        # Convert PubMedArticle to PaperResult
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

        processing_time = int((time.time() - start_time) * 1000)

        return QueryResponse(
            query_id=query_id,
            original_query=query_request.query,
            literature_results=paper_results,
            total_results=len(paper_results),
            processing_time=processing_time
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/status/{query_id}")
async def get_query_status(query_id: str) -> dict:
    """Get status of a query by ID"""

    # Placeholder implementation
    return {
        "query_id": query_id,
        "status": "completed",
        "progress": 100
    }