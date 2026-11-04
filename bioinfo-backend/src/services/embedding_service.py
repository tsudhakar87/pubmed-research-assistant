"""
Semantic relevance scoring with Vertex AI text embeddings.

Kept separate from VertexAIClient (generation) so each can be mocked on its own.
Every failure path degrades to "no scores" rather than failing the query.
"""
import asyncio
import logging
from typing import List, Optional

from ..config.settings import settings
from ..config.vertex_ai import vertex_ai_config
from ..models.response_models import PaperResult
from ..utils.embeddings import cosine_similarity

logger = logging.getLogger(__name__)

# Only the first N papers are scored; the rest keep relevance_score=None.
EMBEDDING_CAP = 50
# Texts per embedding request. Keeps each request well under the per-request token limit.
_BATCH_SIZE = 10
# Title + the opening of the abstract carries the topical signal; 2000 chars is ~500 tokens.
_MAX_CHARS = 2000


class EmbeddingService:
    def __init__(self) -> None:
        self._model = None  # lazy: no Vertex AI calls at import time
        self._unavailable = False

    def _get_model(self):
        if self._model is None:
            import vertexai
            from vertexai.language_models import TextEmbeddingModel

            project_id = vertex_ai_config.project_id or settings.project_id
            if not project_id:
                raise RuntimeError("No GCP project configured for Vertex AI")
            vertexai.init(project=project_id, location=vertex_ai_config.location)
            self._model = TextEmbeddingModel.from_pretrained(vertex_ai_config.embedding_model)
        return self._model

    async def _embed_batch(self, texts: List[str], task_type: str) -> List[List[float]]:
        from vertexai.language_models import TextEmbeddingInput

        model = self._get_model()
        inputs = [TextEmbeddingInput(text=t[:_MAX_CHARS], task_type=task_type) for t in texts]
        results = await asyncio.to_thread(model.get_embeddings, inputs)
        return [r.values for r in results]

    async def get_embeddings(self, texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT") -> List[List[float]]:
        """Embed texts in batches. Returns [] if Vertex AI is unavailable or any batch fails."""
        if not texts or self._unavailable:
            return []
        try:
            batches = [texts[i:i + _BATCH_SIZE] for i in range(0, len(texts), _BATCH_SIZE)]
            results = await asyncio.gather(*(self._embed_batch(b, task_type) for b in batches))
            return [vec for batch in results for vec in batch]
        except (ImportError, RuntimeError) as exc:
            # Not configured (SDK missing or no project): stop trying on every query.
            self._unavailable = True
            logger.warning("Relevance scoring disabled: %s", exc)
            return []
        except Exception as exc:
            logger.warning("Embedding call failed: %s", exc)
            return []

    async def score_relevance(self, query: str, papers: List[PaperResult]) -> List[PaperResult]:
        """
        Score up to EMBEDDING_CAP papers by cosine similarity to the query and sort them
        best-first. Papers beyond the cap follow, unscored, in their original order.
        If embeddings are unavailable, papers are returned unchanged.
        """
        if not papers:
            return papers
        to_score = papers[:EMBEDDING_CAP]
        remainder = papers[EMBEDDING_CAP:]

        query_vecs, doc_vecs = await asyncio.gather(
            self.get_embeddings([query], task_type="RETRIEVAL_QUERY"),
            self.get_embeddings(
                [f"{p.title}. {p.abstract or ''}" for p in to_score],
                task_type="RETRIEVAL_DOCUMENT",
            ),
        )
        if not query_vecs or len(doc_vecs) != len(to_score):
            return papers

        query_vec = query_vecs[0]
        scored = [
            p.model_copy(update={"relevance_score": round(cosine_similarity(query_vec, vec), 4)})
            for p, vec in zip(to_score, doc_vecs)
        ]
        scored.sort(key=lambda p: p.relevance_score or 0.0, reverse=True)
        return scored + remainder


_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Process-wide singleton, matching get_vertex_ai_client()."""
    global _service
    if _service is None:
        _service = EmbeddingService()
    return _service
