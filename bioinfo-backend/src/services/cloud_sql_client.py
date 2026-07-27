"""
Async Cloud SQL / PostgreSQL client using SQLAlchemy 2 + asyncpg.

For local dev:  set DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/bioinfo_db
For Cloud Run:  set DATABASE_URL to the Cloud SQL connection string (same driver prefix).
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text

from ..config.settings import settings
from ..models.database_models import Base

logger = logging.getLogger(__name__)

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def _get_database_url() -> Optional[str]:
    url = settings.database_url
    if not url:
        return None
    # Normalise: plain postgresql:// URLs need the asyncpg driver prefix
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


async def init_db() -> None:
    """Create engine and session factory. Call once at startup."""
    global _engine, _session_factory

    url = _get_database_url()
    if not url:
        logger.warning("DATABASE_URL not set — database features disabled")
        return

    _engine = create_async_engine(
        url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        echo=settings.debug,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    logger.info("Database engine initialised")


async def close_db() -> None:
    """Dispose engine. Call at shutdown."""
    global _engine
    if _engine:
        await _engine.dispose()
        logger.info("Database engine disposed")


async def create_tables() -> None:
    """Create all tables (dev convenience — use Alembic in prod)."""
    if _engine is None:
        return
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")


async def health_check() -> bool:
    """Return True if the database is reachable."""
    if _engine is None:
        return False
    try:
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("Database health check failed", extra={"error": str(e)})
        return False


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager that yields a SQLAlchemy session.

    Usage:
        async with get_session() as session:
            session.add(obj)
            await session.commit()
    """
    if _session_factory is None:
        raise RuntimeError("Database not initialised. Check DATABASE_URL env var.")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def is_db_available() -> bool:
    return _engine is not None
