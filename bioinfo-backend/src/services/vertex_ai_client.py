"""
Vertex AI client for LLM-based text generation and analysis
Uses Google's Gemini models via Vertex AI
"""
from typing import Optional, List, Dict, Any
import os
import json

try:
    import vertexai
    from vertexai.generative_models import GenerativeModel, GenerationConfig
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False

from ..config.settings import settings


class VertexAIClient:
    """
    Client for interacting with Vertex AI Gemini models
    Falls back gracefully if Vertex AI is not available
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: str = "us-central1",
        model_name: str = "gemini-1.5-flash"
    ):
        """
        Initialize Vertex AI client

        Args:
            project_id: GCP project ID (defaults to settings.project_id)
            location: GCP region for Vertex AI
            model_name: Name of the Gemini model to use
        """
        self.project_id = project_id or settings.project_id
        self.location = location
        self.model_name = model_name
        self.available = VERTEX_AI_AVAILABLE and bool(self.project_id)

        if self.available:
            try:
                vertexai.init(project=self.project_id, location=self.location)
                self.model = GenerativeModel(self.model_name)
            except Exception as e:
                print(f"Failed to initialize Vertex AI: {e}")
                self.available = False

    async def generate_text(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """
        Generate text using Vertex AI

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)

        Returns:
            Generated text, or fallback message if unavailable
        """
        if not self.available:
            return "[AI summary unavailable - Vertex AI not configured]"

        try:
            config = GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )

            response = self.model.generate_content(
                prompt,
                generation_config=config
            )

            return response.text

        except Exception as e:
            print(f"Vertex AI generation error: {e}")
            return f"[AI summary error: {str(e)}]"

    async def summarize_papers(
        self,
        papers: List[Dict[str, Any]],
        query: str,
        max_papers: int = 5
    ) -> str:
        """
        Generate a summary of research papers

        Args:
            papers: List of paper dictionaries with title, abstract, etc.
            query: Original user query
            max_papers: Maximum number of papers to include in prompt

        Returns:
            Summary text
        """
        if not papers:
            return "No papers found to summarize."

        # Limit papers to avoid token limits
        papers_subset = papers[:max_papers]

        # Build prompt
        papers_text = ""
        for i, paper in enumerate(papers_subset, 1):
            title = paper.get("title", "Untitled")
            abstract = paper.get("abstract", "No abstract available")
            authors = ", ".join(paper.get("authors", [])[:3])
            year = paper.get("publication_date", "")[:4] if paper.get("publication_date") else "Unknown"

            papers_text += f"\n\n{i}. **{title}**\n"
            papers_text += f"   Authors: {authors} et al.\n"
            papers_text += f"   Year: {year}\n"
            papers_text += f"   Abstract: {abstract[:500]}...\n"

        prompt = f"""You are a scientific research assistant. Based on the following research papers,
provide a concise summary (2-3 paragraphs) that answers the user's query: "{query}"

Focus on:
1. Key findings and themes across the papers
2. Recent developments or trends
3. Practical implications

Research Papers:
{papers_text}

Provide a clear, informative summary:"""

        return await self.generate_text(
            prompt=prompt,
            max_tokens=512,
            temperature=0.5
        )

    async def analyze_query(self, query: str) -> Dict[str, Any]:
        """
        Analyze a research query using LLM

        Args:
            query: User's research question

        Returns:
            Analysis dictionary with extracted information
        """
        if not self.available:
            return {"error": "Vertex AI not available"}

        prompt = f"""Analyze this research query and extract key information:

Query: "{query}"

Provide a JSON response with:
- main_topic: The primary research topic
- key_concepts: List of 3-5 key scientific concepts
- temporal_focus: Whether user wants recent/latest research (true/false)
- specificity: How specific the query is (general/moderate/specific)

Respond ONLY with valid JSON."""

        try:
            response = await self.generate_text(
                prompt=prompt,
                max_tokens=256,
                temperature=0.3
            )

            # Try to parse JSON response
            # Clean potential markdown code blocks
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]

            return json.loads(cleaned.strip())

        except Exception as e:
            print(f"Query analysis error: {e}")
            return {"error": str(e)}


# Global singleton instance
_vertex_ai_client: Optional[VertexAIClient] = None


def get_vertex_ai_client() -> VertexAIClient:
    """Get or create Vertex AI client singleton"""
    global _vertex_ai_client
    if _vertex_ai_client is None:
        _vertex_ai_client = VertexAIClient()
    return _vertex_ai_client
