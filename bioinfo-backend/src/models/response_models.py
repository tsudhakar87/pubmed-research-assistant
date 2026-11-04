from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any
from datetime import datetime
from .request_models import QueryType

Stance = Literal["supports", "contradicts", "mixed", "no_effect", "not_applicable"]
Design = Literal[
    "meta_analysis", "systematic_review", "rct", "clinical_trial",
    "cohort", "case_control", "cross_sectional", "observational",
    "case_report", "review", "animal", "in_vitro", "other",
]
OrganismLabel = Literal["human", "animal", "in_vitro", "mixed", "unknown"]


class Evidence(BaseModel):
    """What one paper's abstract reports, relative to the framed question."""
    design: Design
    design_source: Literal["pubmed", "ai"]
    organism: OrganismLabel
    organism_source: Literal["pubmed", "icite", "ai"]
    sample_size: Optional[int] = None
    population: Optional[str] = None
    intervention: Optional[str] = None
    outcome: Optional[str] = None
    stance: Stance
    key_finding: str
    # Verbatim span from the abstract; None if the model's quote wasn't found in it
    finding_quote: Optional[str] = None
    verified: bool = False


class EvidenceSummary(BaseModel):
    """Counts and facts computed in code from per-paper Evidence (never by the LLM)."""
    question: str
    answerable: bool
    papers_with_evidence: int = 0
    stance_counts: Dict[str, int] = Field(default_factory=dict)
    stance_by_organism: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    design_counts: Dict[str, int] = Field(default_factory=dict)
    by_year: List[Dict[str, int]] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    largest_study: Optional[Dict[str, Any]] = None
    latest_rct_year: Optional[int] = None
    preprint_count: int = 0


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
    # Where the record came from. PubMed records also carry a pmid; preprints don't.
    source: Optional[Literal["pubmed", "biorxiv", "medrxiv"]] = None
    # 1-based position in the backend's ranked list; the synthesis cites papers as [ref]
    ref: Optional[int] = None
    publication_types: List[str] = Field(default_factory=list)
    mesh_terms: List[str] = Field(default_factory=list)
    trial_ids: List[str] = Field(default_factory=list)
    citation_count: Optional[int] = None
    relative_citation_ratio: Optional[float] = None
    evidence: Optional[Evidence] = None
    # Internal: labeled sections for the extraction prompt; not sent to clients
    abstract_sections: Dict[str, str] = Field(default_factory=dict, exclude=True)

class QueryResponse(BaseModel):
    """Main API response"""
    query_id: str
    original_query: str
    refined_query: Optional[str] = None
    query_type: Optional[QueryType] = None
    status: str = "completed"
    literature_results: List[PaperResult] = Field(default_factory=list)
    total_results: int = 0
    processing_time: int  # milliseconds
    ai_summary: Optional[str] = None
    evidence_summary: Optional[EvidenceSummary] = None
    metadata: Optional[Dict[str, Any]] = None

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
