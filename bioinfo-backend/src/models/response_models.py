from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class PaperResult(BaseModel):
    """Individual research paper"""
    title: str
    authors: List[str]
    abstract: Optional[str] = None
    journal: Optional[str] = None
    publication_date: Optional[datetime] = None
    pmid: Optional[str] = None
    doi: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    relevance_score: Optional[float] = None
    
class QueryResponse(BaseModel):
    """Main API response"""
    query_id: str
    original_query: str
    status: str = "completed"
    literature_results: List[PaperResult] = Field(default_factory=list)
    total_results: int = 0
    processing_time: int  # milliseconds
    
    class Config:
        json_schema_extra = {
            "example": {
                "query_id": "q_12345",
                "original_query": "CRISPR developments",
                "status": "completed",
                "literature_results": [
                    {
                        "title": "Advances in CRISPR technology",
                        "authors": ["Jane Doe", "John Smith"],
                        "abstract": "This study explores recent advances...",
                        "journal": "Nature Biotechnology",
                        "publication_date": "2023-05-01T00:00:00",
                        "pmid": "12345678",
                        "doi": "10.1038/example",
                        "keywords": ["CRISPR", "gene editing", "Cas9"],
                        "relevance_score": 0.95
                    }
                ],
                "total_results": 1,
                "processing_time": 150
            }
        }