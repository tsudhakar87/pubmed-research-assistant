"""
WebSocket endpoint at  ws://host/api/v1/ws/query

Protocol (client → server):
  { "query": "...", "max_results": 10, "token": "<jwt>" }

Protocol (server → client):
  { "event": "classifying" }
  { "event": "searching_pubmed" }
  { "event": "retrieving_abstracts" }
  { "event": "synthesizing" }
  { "event": "done", "data": <QueryResponse JSON> }
  { "event": "error", "message": "..." }

The JWT is sent inside the first message because browsers cannot set custom
Authorization headers on WebSocket connections.
"""
import asyncio
import json
import logging
import uuid
from typing import Any, Callable, Coroutine, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ...agents.bioinfo_agent import BioinfoAgent
from ...external.ncbi_client import NCBIClient
from ...models.request_models import BioinformaticsQuery
from ...services.auth_service import decode_access_token, TokenPayload
from ...services.cloud_sql_client import get_session, is_db_available
from ...services.bigquery_client import insert_query_event
from ...models.database_models import Query, QueryPaper
from ...models.response_models import QueryResponse
from ...config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])

ProgressCallback = Callable[[str, Optional[dict]], Coroutine[Any, Any, None]]

_ncbi_client: Optional[NCBIClient] = None
_bioinfo_agent: Optional[BioinfoAgent] = None


def _get_agent() -> BioinfoAgent:
    global _ncbi_client, _bioinfo_agent
    if _ncbi_client is None:
        _ncbi_client = NCBIClient(
            email=settings.ncbi_email,
            api_key=settings.ncbi_api_key,
            tool_name=settings.ncbi_tool_name,
        )
    if _bioinfo_agent is None:
        _bioinfo_agent = BioinfoAgent(_ncbi_client)
    return _bioinfo_agent


async def _persist(
    query_id: str,
    user_id: Optional[uuid.UUID],
    response: QueryResponse,
) -> None:
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
            await session.flush()
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


@router.websocket("/ws/query")
async def websocket_query(websocket: WebSocket) -> None:
    await websocket.accept()
    user: Optional[TokenPayload] = None
    task: Optional[asyncio.Task] = None

    async def send_event(event: str, data: Optional[dict] = None) -> None:
        payload: dict = {"event": event}
        if data:
            payload["data"] = data
        try:
            await websocket.send_json(payload)
        except Exception:
            pass  # client may have already disconnected

    try:
        # ── 1. Receive first message (query + auth token) ─────────────────
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=30)
        msg = json.loads(raw)

        # Authenticate via JWT in the message body
        token = msg.get("token", "")
        if token:
            try:
                payload = decode_access_token(token)
                user = TokenPayload(payload)
            except Exception:
                await send_event("error", {"message": "Invalid or expired token"})
                await websocket.close(code=4001)
                return
        else:
            await send_event("error", {"message": "Authentication required — include 'token' in first message"})
            await websocket.close(code=4001)
            return

        query_text = msg.get("query", "").strip()
        if not query_text:
            await send_event("error", {"message": "Missing 'query' field"})
            await websocket.close(code=4000)
            return

        max_results = int(msg.get("max_results", 10))
        query_id = f"q_{uuid.uuid4().hex[:8]}"
        agent = _get_agent()

        # ── 2. Run the pipeline with progress events ──────────────────────

        async def run_pipeline() -> None:
            await send_event("classifying")
            query_request = BioinformaticsQuery(query=query_text, max_results=max_results)

            response = await agent.process_query(
                query_request=query_request,
                query_id=query_id,
                include_ai_summary=True,
                progress_callback=send_event,
            )

            await _persist(query_id, user.user_id if user else None, response)
            await send_event("done", response.model_dump(mode="json"))

        task = asyncio.create_task(run_pipeline())

        # ── 3. Keep connection alive until pipeline finishes or client leaves
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.exception("Pipeline error", extra={"query_id": query_id})
            await send_event("error", {"message": str(exc)})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
        if task and not task.done():
            task.cancel()
    except asyncio.TimeoutError:
        await send_event("error", {"message": "Timed out waiting for query"})
        await websocket.close(code=4000)
    except json.JSONDecodeError:
        await send_event("error", {"message": "Invalid JSON in first message"})
        await websocket.close(code=4000)
    except Exception:
        logger.exception("Unexpected WebSocket error")
        await send_event("error", {"message": "Internal server error"})
    finally:
        if task and not task.done():
            task.cancel()
