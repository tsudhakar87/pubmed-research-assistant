"""
Async Gemini client on the google-genai SDK (Vertex AI backend).

Replaces vertexai.generative_models for new code: that module is deprecated, and
VertexAIClient calls its synchronous generate_content() from async code, which
blocks the event loop for the whole generation. This client uses client.aio.

Every method returns None on failure so callers can degrade gracefully.
"""
import logging
from typing import Optional, Type, TypeVar

from pydantic import BaseModel

from ..config.settings import settings
from ..config.vertex_ai import vertex_ai_config

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class GeminiClient:
    def __init__(
        self,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.project_id = project_id or vertex_ai_config.project_id or settings.project_id
        self.location = location or vertex_ai_config.location
        self.model_name = model_name or vertex_ai_config.model_name
        self._client = None
        self._failed = False

    @property
    def available(self) -> bool:
        return bool(self.project_id) and not self._failed

    def _get_client(self):
        if self._client is None:
            try:
                from google import genai
                self._client = genai.Client(vertexai=True, project=self.project_id, location=self.location)
            except Exception as exc:
                self._failed = True
                logger.warning("Gemini client unavailable: %s", exc)
                raise
        return self._client

    async def _generate(self, prompt: str, config: dict):
        from google.genai import types

        client = self._get_client()
        return await client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(**config),
        )

    async def generate_text(
        self, prompt: str, temperature: float = 0.3, max_tokens: int = 2048
    ) -> Optional[str]:
        if not self.available:
            return None
        try:
            response = await self._generate(prompt, {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            })
            return (response.text or "").strip() or None
        except Exception as exc:
            logger.warning("Gemini text generation failed: %s", exc)
            return None

    async def generate_json(
        self, prompt: str, schema: Type[T], temperature: float = 0.1, max_tokens: int = 8192
    ) -> Optional[T]:
        """Structured output validated against a Pydantic model."""
        if not self.available:
            return None
        try:
            response = await self._generate(prompt, {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                "response_mime_type": "application/json",
                "response_schema": schema,
            })
            if isinstance(response.parsed, schema):
                return response.parsed
            return schema.model_validate_json(response.text or "")
        except Exception as exc:
            logger.warning("Gemini JSON generation failed (%s): %s", schema.__name__, exc)
            return None


_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client
