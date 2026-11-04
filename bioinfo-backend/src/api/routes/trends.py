"""
GET /api/v1/trends?q=<query>&years=10

Publication counts per year for a topic, from one count-only PubMed ESearch per year.
These are counts over all of PubMed, not a histogram of the (small) result set, so the
chart shows how much a field has been publishing over time.
"""
import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, Query as QParam

from ...external.ncbi_client import NCBIClient
from ...services.auth_service import TokenPayload, get_current_user
from .query import get_ncbi_client

router = APIRouter(prefix="/trends", tags=["Research"])


@router.get("")
async def get_trend_data(
    q: str = QParam(..., min_length=3, max_length=500),
    years: int = QParam(default=10, ge=1, le=20),
    ncbi_client: NCBIClient = Depends(get_ncbi_client),
    _: TokenPayload = Depends(get_current_user),
) -> dict:
    """
    Paper counts per publication year for the past `years` years, oldest first.
    The current year is partial (year to date) and flagged with `partial: true`.
    """
    current_year = datetime.now().year
    year_range = range(current_year - years + 1, current_year + 1)

    # Requests still go through the client's NCBI rate limiter one at a time.
    counts = await asyncio.gather(*(
        ncbi_client.count(q, min_date=f"{year}/01/01", max_date=f"{year}/12/31")
        for year in year_range
    ))

    return {
        "query": q,
        "data": [
            {"year": year, "count": count, "partial": year == current_year}
            for year, count in zip(year_range, counts)
        ],
    }
