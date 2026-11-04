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
from ...services.bigquery_client import insert_query_event
from ...models.database_models import Query, QueryPaper

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


async def _persist_query(
    query_id: str,
    user_id: Optional[uuid.UUID],
    response: QueryResponse,
) -> None:
    """Save query + paper results to Postgres and log event to BigQuery."""
    if is_db_available():
        async with get_session() as session:
            query_row = Query(
                query_id=query_id,
                user_id=user_id,
                original_query=response.original_query,
                refined_query=response.refined_query,
                query_type=response.query_type.value if response.query_type else None,
                status=response.status,
                total_results=response.total_results,
                processing_time_ms=response.processing_time,
                ai_summary=response.ai_summary,
                result_json=response.model_dump(mode="json"),
            )
            session.add(query_row)
            await session.flush()  # get query_row.id

            for rank, paper in enumerate(response.literature_results):
                session.add(QueryPaper(
                    query_id=query_row.id,
                    pmid=paper.pmid or "",
                    title=paper.title,
                    authors=paper.authors,
                    journal=paper.journal,
                    publication_date=(
                        paper.publication_date.isoformat() if paper.publication_date else None
                    ),
                    abstract=paper.abstract,
                    doi=paper.doi,
                    keywords=paper.keywords,
                    relevance_score=paper.relevance_score,
                    rank=rank,
                    source=paper.source,
                ))

    await insert_query_event(
        query_id=query_id,
        user_id=user_id,
        original_query=response.original_query,
        query_type=response.query_type.value if response.query_type else None,
        total_results=response.total_results,
        processing_time_ms=response.processing_time,
        has_ai_summary=bool(response.ai_summary),
    )


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

    await _persist_query(query_id, current_user.user_id, response)
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
    from ...models.response_models import EvidenceSummary, PaperResult

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

    # Stored JSON is a dumped QueryResponse, so models round-trip (older rows simply
    # lack the newer fields, which default to empty)
    papers = []
    for p in papers_raw:
        try:
            papers.append(PaperResult.model_validate(p))
        except Exception:
            continue

    evidence_summary = None
    if stored.get("evidence_summary"):
        try:
            evidence_summary = EvidenceSummary.model_validate(stored["evidence_summary"])
        except Exception:
            evidence_summary = None

    synthesizer = ResponseSynthesizer()
    new_summary = await synthesizer.synthesize_summary(
        papers=papers,
        original_query=stored.get("original_query", ""),
        evidence_summary=evidence_summary,
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
