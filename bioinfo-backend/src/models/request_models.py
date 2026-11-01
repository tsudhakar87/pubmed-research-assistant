from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class QueryType(str, Enum):
    LITERATURE = "literature"
    SEQUENCE = "sequence"
    GENERAL = "general"

class BioinformaticsQuery(BaseModel):
    """User query for research"""
    query: str = Field(..., min_length=3, max_length=500, description="research question")
    query_type: Optional[QueryType] = Field(None, description="auto-detected if not provided")
    max_results: int = Field(20, ge=1, le=100, description="maximum number of results to return")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are the latest research findings on CRISPR gene editing?",
                "query_type": "literature",
                "max_results": 20
            }
        }
