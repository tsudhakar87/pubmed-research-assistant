"""
BigQuery client for query analytics.
Inserts a row for every completed research query so we can analyze
usage patterns, popular topics, and performance over time.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from ..config.settings import settings

logger = logging.getLogger(__name__)

try:
    from google.cloud import bigquery
    _BQ_AVAILABLE = True
except ImportError:
    _BQ_AVAILABLE = False


_client: Optional[Any] = None  # google.cloud.bigquery.Client


def _get_client():
    global _client
    if not _BQ_AVAILABLE:
        return None
    if _client is None:
        try:
            _client = bigquery.Client(project=settings.project_id)
        except Exception as e:
            logger.warning("BigQuery client init failed", extra={"error": str(e)})
            return None
    return _client


def _table_ref(table_name: str) -> str:
    return f"{settings.project_id}.{settings.bigquery_dataset}.{table_name}"


async def insert_query_event(
    *,
    query_id: str,
    user_id: Optional[UUID],
    original_query: str,
    query_type: Optional[str],
    total_results: int,
    processing_time_ms: int,
    has_ai_summary: bool,
) -> None:
    """
    Insert one row into the query_events BigQuery table.
    Fails silently so analytics never blocks the main request path.
    """
    client = _get_client()
    if client is None:
        return

    row = {
        "query_id": query_id,
        "user_id": str(user_id) if user_id else None,
        "original_query": original_query,
        "query_type": query_type,
        "total_results": total_results,
        "processing_time_ms": processing_time_ms,
        "has_ai_summary": has_ai_summary,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        errors = client.insert_rows_json(_table_ref("query_events"), [row])
        if errors:
            logger.warning("BigQuery insert errors", extra={"errors": errors})
    except Exception as e:
        logger.warning("BigQuery insert failed", extra={"error": str(e)})


async def ensure_table_exists() -> None:
    """Create the query_events table if it doesn't exist yet."""
    client = _get_client()
    if client is None:
        return

    schema = [
        bigquery.SchemaField("query_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("user_id", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("original_query", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("query_type", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("total_results", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("processing_time_ms", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("has_ai_summary", "BOOLEAN", mode="NULLABLE"),
        bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
    ]

    table = bigquery.Table(_table_ref("query_events"), schema=schema)
    table.time_partitioning = bigquery.TimePartitioning(field="created_at")

    try:
        client.create_table(table, exists_ok=True)
        logger.info("BigQuery query_events table ready")
    except Exception as e:
        logger.warning("BigQuery table creation failed", extra={"error": str(e)})
