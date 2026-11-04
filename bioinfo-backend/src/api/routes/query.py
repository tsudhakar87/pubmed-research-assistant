import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends

from ...models.request_models import BioinformaticsQuery
from ...models.response_models import QueryResponse
from ...config.settings import settings
from ...external.ncbi_client import NCBIClient
from ...agents.bioinfo_agent import BioinfoAgent
from ...services.auth_service import TokenPayload, get_current_user
from ...services.cloud_sql_client import get_session, is_db_available
from ...services.query_store import mark_unsaved, save_query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/query", tags=["Research"])

_ncbi_client: Optional[NCBIClient] = None
_bioinfo_agent: Optional[BioinfoAgent] = None


async def get_ncbi_client() -> NCBIClient:
    global _ncbi_client
    if _ncbi_client is None:
        _ncbi_client = NCBIClient(
            email=settings.ncbi_email,
            api_key=settings.ncbi_api_key,
            tool_name=settings.ncbi_tool_name,
        )
    return _ncbi_client


async def get_bioinfo_agent() -> BioinfoAgent:
    global _bioinfo_agent
    if _bioinfo_agent is None:
        ncbi_client = await get_ncbi_client()
        _bioinfo_agent = BioinfoAgent(ncbi_client)
    return _bioinfo_agent


@router.post("/research", response_model=QueryResponse)
async def research_query(
    query_request: BioinformaticsQuery,
    agent: BioinfoAgent = Depends(get_bioinfo_agent),
    current_user: TokenPayload = Depends(get_current_user),
) -> QueryResponse:
    """
    Submit a research query and fetch results from PubMed.

    Pipeline:
    1. Classify query (detect temporal requirements, query type)
    2. Search PubMed, bioRxiv and medRxiv in parallel
    3. Rank by semantic relevance
    4. Generate AI synthesis via Gemini
    5. Persist query + results to Cloud SQL and log event to BigQuery
    """
    query_id = f"q_{uuid.uuid4().hex[:8]}"
    logger.info(
        "Research query received",
        extra={"query_id": query_id, "user_id": str(current_user.user_id)},
    )

    response = await agent.process_query(
        query_request=query_request,
        query_id=query_id,
        include_ai_summary=True,
    )

    if not await save_query(query_id, current_user.user_id, response):
        response = mark_unsaved(response)
    return response


@router.get("/history")
async def get_query_history(
    current_user: TokenPayload = Depends(get_current_user),
    limit: int = 50,
) -> dict:
    """Return the authenticated user's past queries, newest first."""
    if not is_db_available():
        return {"queries": []}

    from sqlalchemy import select
    from ...models.database_models import Query as QueryRow

    async with get_session() as session:
        result = await session.execute(
            select(QueryRow)
            .where(QueryRow.user_id == current_user.user_id)
            .order_by(QueryRow.created_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()

    return {
        "queries": [
            {
                "query_id": r.query_id,
                "original_query": r.original_query,
                "query_type": r.query_type,
                "total_results": r.total_results,
                "created_at": r.created_at.isoformat(),
                "has_ai_summary": bool(r.ai_summary),
            }
            for r in rows
        ]
    }


@router.post("/{query_id}/synthesize")
async def regenerate_summary(
    query_id: str,
    current_user: TokenPayload = Depends(get_current_user),
) -> dict:
    """Re-run AI synthesis on the stored papers for a past query and persist the result."""
    if not is_db_available():
        return {"error": "Database not available"}

    from sqlalchemy import select
    from ...models.database_models import Query as QueryRow
    from ...utils.error_handlers import NotFoundError
    from ...agents.response_synthesizer import ResponseSynthesizer
    from ...models.response_models import PaperResult
    from datetime import datetime

    async with get_session() as session:
        result = await session.execute(
            select(QueryRow).where(
                QueryRow.query_id == query_id,
                QueryRow.user_id == current_user.user_id,
            )
        )
        row = result.scalar_one_or_none()

    if row is None:
        raise NotFoundError("Query", query_id)

    stored = row.result_json or {}
    papers_raw = stored.get("literature_results", [])
    if not papers_raw:
        return {"ai_summary": None}

    papers = []
    for p in papers_raw:
        try:
            pub_date = datetime.fromisoformat(p["publication_date"]) if p.get("publication_date") else None
            papers.append(PaperResult(
                title=p.get("title", ""),
                authors=p.get("authors", []),
                abstract=p.get("abstract"),
                journal=p.get("journal"),
                publication_date=pub_date,
                pmid=p.get("pmid"),
                doi=p.get("doi"),
                keywords=p.get("keywords", []),
                source=p.get("source"),
            ))
        except Exception:
            continue

    synthesizer = ResponseSynthesizer()
    new_summary = await synthesizer.synthesize_summary(
        papers=papers,
        original_query=stored.get("original_query", ""),
    )

    # Persist updated summary
    async with get_session() as session:
        result = await session.execute(
            select(QueryRow).where(QueryRow.query_id == query_id)
        )
        row = result.scalar_one_or_none()
        if row:
            row.ai_summary = new_summary
            updated_json = dict(row.result_json or {})
            updated_json["ai_summary"] = new_summary
            row.result_json = updated_json

    return {"ai_summary": new_summary}


@router.get("/history/{query_id}")
async def reopen_query(
    query_id: str,
    current_user: TokenPayload = Depends(get_current_user),
) -> dict:
    """Retrieve full cached result for a past query."""
    if not is_db_available():
        return {"error": "Database not available"}

    from sqlalchemy import select
    from ...models.database_models import Query as QueryRow
    from ...utils.error_handlers import NotFoundError

    async with get_session() as session:
        result = await session.execute(
            select(QueryRow).where(
                QueryRow.query_id == query_id,
                QueryRow.user_id == current_user.user_id,
            )
        )
        row = result.scalar_one_or_none()

    if row is None:
        raise NotFoundError("Query", query_id)

    return row.result_json or {}
