from fastapi import APIRouter, HTTPException, Depends
import uuid
from typing import Optional

from ...models.request_models import BioinformaticsQuery
from ...models.response_models import QueryResponse
from ...config.settings import settings
from ...external.ncbi_client import NCBIClient
from ...agents.bioinfo_agent import BioinfoAgent

router = APIRouter(prefix="/query", tags=["Research"])

# NCBI client singleton
_ncbi_client: Optional[NCBIClient] = None
_bioinfo_agent: Optional[BioinfoAgent] = None


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


async def get_bioinfo_agent() -> BioinfoAgent:
    """Dependency to get BioinfoAgent instance"""
    global _bioinfo_agent
    if _bioinfo_agent is None:
        ncbi_client = await get_ncbi_client()
        _bioinfo_agent = BioinfoAgent(ncbi_client)
    return _bioinfo_agent


@router.post("/research", response_model=QueryResponse)
async def research_query(
    query_request: BioinformaticsQuery,
    agent: BioinfoAgent = Depends(get_bioinfo_agent)
) -> QueryResponse:
    """
    Submit a research query and fetch results from PubMed

    The agent will:
    1. Analyze the query to detect temporal requirements (e.g., "latest" = last 2 years)
    2. Search PubMed with optimized parameters (date filtering, sorting)
    3. Generate AI-powered summary of results (if Vertex AI is configured)
    """
    query_id = f"q_{uuid.uuid4().hex[:8]}"

    try:
        # Process query through the bioinfo agent
        response = await agent.process_query(
            query_request=query_request,
            query_id=query_id,
            include_ai_summary=True  # Enable AI summaries (gracefully falls back if unavailable)
        )

        return response

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