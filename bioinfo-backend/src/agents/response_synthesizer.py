"""
Response synthesizer that generates AI-powered summaries of research results
"""
from typing import List, Optional
from ..models.response_models import PaperResult
from ..services.vertex_ai_client import get_vertex_ai_client


class ResponseSynthesizer:
    """Synthesizes research results into coherent summaries"""

    def __init__(self):
        self.vertex_client = get_vertex_ai_client()

    async def synthesize_summary(
        self,
        papers: List[PaperResult],
        original_query: str,
        include_ai_summary: bool = True
    ) -> Optional[str]:
        """
        Generate a summary of research papers

        Args:
            papers: List of paper results
            original_query: User's original query
            include_ai_summary: Whether to generate AI summary (requires Vertex AI)

        Returns:
            Summary text or None if disabled/unavailable
        """
        if not include_ai_summary or not papers:
            return None

        # Convert PaperResult objects to dicts for the AI client
        papers_dict = [
            {
                "title": paper.title,
                "abstract": paper.abstract,
                "authors": paper.authors,
                "publication_date": paper.publication_date.isoformat() if paper.publication_date else None,
                "journal": paper.journal,
                "pmid": paper.pmid
            }
            for paper in papers
        ]

        summary = await self.vertex_client.summarize_papers(
            papers=papers_dict,
            query=original_query,
            max_papers=5
        )

        return summary

    def format_papers_text_summary(self, papers: List[PaperResult]) -> str:
        """
        Generate a text-based summary without AI (fallback)

        Args:
            papers: List of paper results

        Returns:
            Formatted text summary
        """
        if not papers:
            return "No papers found."

        summary_lines = [f"Found {len(papers)} relevant papers:"]

        for i, paper in enumerate(papers[:5], 1):
            # Handle publication_date - it's a datetime object, not a string
            year = "Unknown"
            if paper.publication_date:
                year = str(paper.publication_date.year) if hasattr(paper.publication_date, 'year') else str(paper.publication_date)[:4]

            authors = ", ".join(paper.authors[:2]) if paper.authors else "Unknown authors"

            summary_lines.append(
                f"\n{i}. {paper.title}\n"
                f"   {authors} et al. ({year})\n"
                f"   {paper.journal or 'Journal unknown'}"
            )

        if len(papers) > 5:
            summary_lines.append(f"\n... and {len(papers) - 5} more papers.")

        return "\n".join(summary_lines)
