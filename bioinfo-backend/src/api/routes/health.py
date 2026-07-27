import logging
from fastapi import APIRouter
from datetime import datetime

router = APIRouter(prefix="/health", tags=["Health"])
logger = logging.getLogger(__name__)


@router.get("/")
async def health_check():
    """Simple health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "bioinfo-api"
    }


@router.get("/detailed")
async def detailed_health():
    """Detailed health check with dependency status."""
    import os

    vertex_status = "unchecked"
    try:
        from ...services.vertex_ai_client import get_vertex_ai_client
        client = get_vertex_ai_client()
        vertex_status = "ok" if client.available else "unavailable"
    except Exception:
        vertex_status = "error"

    db_status = "unchecked"
    try:
        from ...services.cloud_sql_client import health_check
        db_status = "ok" if await health_check() else "unavailable"
    except Exception:
        db_status = "error"

    return {
        "status": "healthy",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "timestamp": datetime.now().isoformat(),
        "vertex_ai": vertex_status,
        "database": db_status,
    }
