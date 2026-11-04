"""
Saving completed queries: Postgres (history) plus a BigQuery analytics event.

Saving must never cost the user their results. A database error (for example a
missing migration) is logged and reported back as `saved=False` so the caller
can still return the response and tell the user it isn't in their history.
"""
import logging
import uuid
from typing import Optional

from ..models.database_models import Query, QueryPaper
from ..models.response_models import QueryResponse
from .bigquery_client import insert_query_event
from .cloud_sql_client import get_session, is_db_available

logger = logging.getLogger(__name__)


async def _save_to_db(query_id: str, user_id: Optional[uuid.UUID], response: QueryResponse) -> None:
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
        await session.flush()  # assigns query_row.id

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


async def save_query(
    query_id: str,
    user_id: Optional[uuid.UUID],
    response: QueryResponse,
) -> bool:
    """
    Persist the query and log the analytics event. Never raises.
    Returns False if the database save failed (True if it succeeded or no DB is configured).
    """
    saved = True
    if is_db_available():
        try:
            await _save_to_db(query_id, user_id, response)
        except Exception:
            saved = False
            logger.exception("Failed to save query to the database", extra={"query_id": query_id})

    await insert_query_event(
        query_id=query_id,
        user_id=user_id,
        original_query=response.original_query,
        query_type=response.query_type.value if response.query_type else None,
        total_results=response.total_results,
        processing_time_ms=response.processing_time,
        has_ai_summary=bool(response.ai_summary),
    )
    return saved


def mark_unsaved(response: QueryResponse) -> QueryResponse:
    """Flag a response whose history save failed, for the UI to mention."""
    return response.model_copy(update={"metadata": {**(response.metadata or {}), "history_saved": False}})
