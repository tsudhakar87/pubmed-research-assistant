"""
Vertex AI configuration loaded from environment variables.
"""
import os
from dataclasses import dataclass


@dataclass
class VertexAIConfig:
    project_id: str
    location: str
    model_name: str
    embedding_model: str


def get_vertex_ai_config() -> VertexAIConfig:
    return VertexAIConfig(
        project_id=os.environ.get("PROJECT_ID", ""),
        location=os.environ.get("VERTEX_AI_LOCATION", "us-central1"),
        model_name=os.environ.get("VERTEX_AI_MODEL", "gemini-2.5-flash"),
        embedding_model=os.environ.get("VERTEX_AI_EMBEDDING_MODEL", "text-embedding-004"),
    )


def _lazy_config():
    return get_vertex_ai_config()

class _LazyConfig:
    """Defers reading env vars until first attribute access."""
    _inner = None

    def _load(self):
        if self._inner is None:
            self._inner = get_vertex_ai_config()
        return self._inner

    def __getattr__(self, name):
        return getattr(self._load(), name)

vertex_ai_config = _LazyConfig()
