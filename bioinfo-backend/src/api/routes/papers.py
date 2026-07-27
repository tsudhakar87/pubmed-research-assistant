"""
Paper-centric routes:
  GET  /api/v1/papers/{pmid}              — single paper detail
  POST /api/v1/papers/compare             — compare 2–3 papers (AI diff synthesis)
  GET  /api/v1/papers/{pmid}/score-variant — BioNeMo Evo2 variant scoring
  GET  /api/v1/query/similar              — semantically similar past queries
"""
import asyncio
import logging
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ...external.ncbi_client import NCBIClient
from ...services.auth_service import TokenPayload, get_current_user
from ...services.vertex_ai_client import get_vertex_ai_client
from ...utils.variant_detection import detect_variants
from ...utils.error_handlers import NotFoundError, ExternalServiceError
from ...config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Papers"])

NVIDIA_API_KEY: str = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_EVO2_URL: str = "https://health.api.nvidia.com/v1/biology/arc/evo2-40b/score"
BIONEMO_TIMEOUT: float = 30.0  # seconds

_ncbi_client: Optional[NCBIClient] = None


def _get_ncbi() -> NCBIClient:
    global _ncbi_client
    if _ncbi_client is None:
        _ncbi_client = NCBIClient(
            email=settings.ncbi_email,
            api_key=settings.ncbi_api_key,
            tool_name=settings.ncbi_tool_name,
        )
    return _ncbi_client


# ── Paper detail ──────────────────────────────────────────────────────────────

@router.get("/papers/{pmid}")
async def get_paper(
    pmid: str,
    current_user: TokenPayload = Depends(get_current_user),
) -> dict:
    """Fetch a single paper's full details from PubMed by PMID."""
    ncbi = _get_ncbi()
    articles = await ncbi.fetch_articles([pmid])
    if not articles:
        raise NotFoundError("Paper", pmid)

    article = articles[0]
    abstract_text = article.abstract or ""
    variants = detect_variants(abstract_text)

    return {
        "pmid": article.pmid,
        "title": article.title,
        "authors": article.authors,
        "journal": article.journal,
        "publication_date": article.publication_date.isoformat() if article.publication_date else None,
        "abstract": abstract_text,
        "doi": article.doi,
        "keywords": article.keywords,
        "detected_variants": variants,
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{article.pmid}/",
    }


# ── Paper comparison ──────────────────────────────────────────────────────────

class CompareRequest(BaseModel):
    pmids: list[str]


@router.post("/papers/compare")
async def compare_papers(
    body: CompareRequest,
    current_user: TokenPayload = Depends(get_current_user),
) -> dict:
    """
    Compare 2–3 papers side-by-side with an AI diff synthesis that highlights
    agreeing and diverging claims.
    """
    if len(body.pmids) < 2 or len(body.pmids) > 3:
        from ...utils.error_handlers import ValidationError
        raise ValidationError("Provide 2 or 3 PMIDs to compare")

    ncbi = _get_ncbi()
    articles = await ncbi.fetch_articles(body.pmids)

    if len(articles) < 2:
        raise NotFoundError("Papers", str(body.pmids))

    papers_info = [
        {
            "pmid": a.pmid,
            "title": a.title,
            "authors": a.authors[:3],
            "journal": a.journal,
            "publication_date": a.publication_date.isoformat() if a.publication_date else None,
            "abstract": a.abstract or "",
            "detected_variants": detect_variants(a.abstract or ""),
        }
        for a in articles
    ]

    # AI diff synthesis
    ai_client = get_vertex_ai_client()
    papers_text = "\n\n".join(
        f"Paper {i+1} — {p['title']} (PMID {p['pmid']}):\n{p['abstract'][:800]}"
        for i, p in enumerate(papers_info)
    )
    prompt = f"""You are a scientific research assistant. Compare the following {len(papers_info)} papers.

{papers_text}

Write a concise paragraph (3-5 sentences) that:
1. Identifies the main claim or finding they AGREE on (label as agreeing)
2. Identifies the key point(s) where they DIVERGE or contradict (label as diverging)
3. Explains the mechanism or reason for the divergence if apparent

Be specific — cite the actual biological mechanisms, not just "they agree on X"."""

    synthesis = await ai_client.generate_text(prompt, max_tokens=2048, temperature=0.3)

    return {
        "papers": papers_info,
        "ai_diff_synthesis": synthesis,
    }


# ── BioNeMo variant scoring ───────────────────────────────────────────────────

@router.get("/papers/{pmid}/score-variant")
async def score_variant(
    pmid: str,
    variant: str = Query(..., description="Variant notation, e.g. V600E or c.1799T>A"),
    gene: Optional[str] = Query(None, description="Gene symbol, e.g. BRAF"),
    current_user: TokenPayload = Depends(get_current_user),
) -> dict:
    """
    Score a variant using NVIDIA BioNeMo Evo2-40b NIM.
    Returns predicted effect (Δ likelihood) and classification.
    """
    if not NVIDIA_API_KEY:
        raise ExternalServiceError("BioNeMo", "NVIDIA_API_KEY not configured")

    payload = {
        "variant": variant,
        "gene": gene,
        "model": "evo2-40b",
    }

    try:
        async with httpx.AsyncClient(timeout=BIONEMO_TIMEOUT) as client:
            resp = await client.post(
                NVIDIA_EVO2_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {NVIDIA_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            result = resp.json()
    except httpx.TimeoutException:
        raise ExternalServiceError("BioNeMo Evo2", "Request timed out (>30s)")
    except httpx.HTTPStatusError as e:
        raise ExternalServiceError("BioNeMo Evo2", f"HTTP {e.response.status_code}")
    except Exception as e:
        raise ExternalServiceError("BioNeMo Evo2", str(e))

    score: float = result.get("score", result.get("delta_likelihood", 0.0))
    classification = "disruptive" if score >= 0.7 else ("neutral" if score <= 0.3 else "moderate")

    return {
        "pmid": pmid,
        "variant": variant,
        "gene": gene,
        "score": round(score, 3),
        "classification": classification,
        "sequence_context": result.get("sequence_context"),
        "model": "evo2-40b",
        "source": "BioNeMo NIM",
    }


# ── Similar queries (vector search) ──────────────────────────────────────────

@router.get("/query/similar")
async def similar_queries(
    q: str = Query(..., description="Query text to find similar past queries for"),
    limit: int = Query(5, ge=1, le=20),
    current_user: TokenPayload = Depends(get_current_user),
) -> dict:
    """
    Return past queries semantically similar to the given text.
    Uses Vertex AI embeddings + cosine similarity over stored query embeddings.
    Falls back to recent queries if embeddings are not available.
    """
    from ...services.cloud_sql_client import get_session, is_db_available
    from ...models.database_models import Query as QueryRow
    from sqlalchemy import select

    if not is_db_available():
        return {"queries": [], "method": "unavailable"}

    # Try embedding-based similarity first
    ai_client = get_vertex_ai_client()

    async with get_session() as session:
        # Fetch recent queries for this user that have embeddings
        result = await session.execute(
            select(QueryRow)
            .where(
                QueryRow.user_id == current_user.user_id,
                QueryRow.embedding.isnot(None),
            )
            .order_by(QueryRow.created_at.desc())
            .limit(200)
        )
        candidates = result.scalars().all()

    if not candidates:
        # Fallback: return most recent queries by date
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
                    "created_at": r.created_at.isoformat(),
                    "total_results": r.total_results,
                }
                for r in rows
            ],
            "method": "recency_fallback",
        }

    # Compute cosine similarity
    import numpy as np

    q_embedding = await _embed(q)
    if q_embedding is None:
        return {"queries": [], "method": "embedding_unavailable"}

    q_vec = np.array(q_embedding)
    q_norm = np.linalg.norm(q_vec)

    scored = []
    for row in candidates:
        emb = np.array(row.embedding)
        sim = float(np.dot(q_vec, emb) / (q_norm * np.linalg.norm(emb) + 1e-9))
        scored.append((sim, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:limit]

    return {
        "queries": [
            {
                "query_id": r.query_id,
                "original_query": r.original_query,
                "created_at": r.created_at.isoformat(),
                "total_results": r.total_results,
                "similarity": round(sim, 4),
            }
            for sim, r in top
        ],
        "method": "embedding_similarity",
    }


async def _embed(text: str) -> Optional[list]:
    """Generate a text embedding using Vertex AI. Returns None on failure."""
    try:
        from vertexai.language_models import TextEmbeddingModel
        model = TextEmbeddingModel.from_pretrained("text-embedding-004")
        embeddings = model.get_embeddings([text])
        return embeddings[0].values
    except Exception as e:
        logger.warning("Embedding failed", extra={"error": str(e)})
        return None
