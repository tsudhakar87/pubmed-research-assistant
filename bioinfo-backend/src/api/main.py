# FastAPI application for backend
# Load .env as early as possible so all os.environ.get() calls see the values
import os
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / ".env")
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# routes
from .routes import health, query, auth, websocket, papers
from ..config.settings import settings
from ..utils.logging_config import configure_logging
from ..utils.error_handlers import register_error_handlers
from ..services.cloud_sql_client import init_db, close_db, create_tables
from ..services.bigquery_client import ensure_table_exists

# Configure logging first so all subsequent imports log correctly
configure_logging(environment=settings.environment)

import logging
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PubMed Research Assistant",
    description="API for PubMed search, AI synthesis, variant scoring, and research analytics",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Register global error handlers
register_error_handlers(app)

# Configure CORS origins
cors_origins = settings.cors_origins.copy()
additional_origins = os.getenv("CORS_ORIGINS", "")
if additional_origins:
    cors_origins.extend(additional_origins.split(","))

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# include routers in app
app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(query.router, prefix="/api/v1")
app.include_router(websocket.router, prefix="/api/v1")
app.include_router(papers.router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    logger.info("PubMed Research Assistant starting up", extra={"environment": settings.environment})
    await init_db()
    await create_tables()
    await ensure_table_exists()


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("PubMed Research Assistant shutting down")
    await close_db()


@app.get("/")
async def root():
    return {
        "message": "PubMed Research Assistant API",
        "status": "running",
        "docs": "/docs",
        "health": "/api/v1/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080, reload=True)
