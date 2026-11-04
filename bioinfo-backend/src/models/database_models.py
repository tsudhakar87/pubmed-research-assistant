"""
SQLAlchemy ORM models for persisting queries, results, and users.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    String, Text, Integer, Float, DateTime, Boolean,
    ForeignKey, JSON, Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    google_sub: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    picture_url: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    queries: Mapped[list["Query"]] = relationship("Query", back_populates="user", lazy="select")


class Query(Base):
    __tablename__ = "queries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    query_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    original_query: Mapped[str] = mapped_column(Text, nullable=False)
    refined_query: Mapped[Optional[str]] = mapped_column(Text)
    query_type: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    total_results: Mapped[int] = mapped_column(Integer, default=0)
    processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text)
    # Store full result list as JSON for fast retrieval
    result_json: Mapped[Optional[dict]] = mapped_column(JSON)
    # Embedding vector stored separately in pgvector / Cloud SQL
    embedding: Mapped[Optional[list]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    user: Mapped[Optional["User"]] = relationship("User", back_populates="queries")
    papers: Mapped[list["QueryPaper"]] = relationship("QueryPaper", back_populates="query", lazy="select")

    __table_args__ = (
        Index("ix_queries_user_created", "user_id", "created_at"),
    )


class QueryPaper(Base):
    """Junction table linking a query to each paper (PubMed or preprint) it returned."""

    __tablename__ = "query_papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("queries.id", ondelete="CASCADE"), nullable=False
    )
    pmid: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text)
    authors: Mapped[Optional[list]] = mapped_column(JSON)
    journal: Mapped[Optional[str]] = mapped_column(String(255))
    publication_date: Mapped[Optional[str]] = mapped_column(String(20))
    abstract: Mapped[Optional[str]] = mapped_column(Text)
    doi: Mapped[Optional[str]] = mapped_column(String(255))
    keywords: Mapped[Optional[list]] = mapped_column(JSON)
    relevance_score: Mapped[Optional[float]] = mapped_column(Float)
    # Detected variant mentions in abstract (e.g. ["BRAF V600E"])
    detected_variants: Mapped[Optional[list]] = mapped_column(JSON)
    rank: Mapped[int] = mapped_column(Integer, default=0)
    # "pubmed" | "biorxiv" | "medrxiv". Preprint rows store pmid as "".
    source: Mapped[Optional[str]] = mapped_column(String(20))

    query: Mapped["Query"] = relationship("Query", back_populates="papers")

    __table_args__ = (
        Index("ix_query_papers_pmid", "pmid"),
        Index("ix_query_papers_query_id", "query_id"),
    )
