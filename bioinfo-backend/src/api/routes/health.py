from fastapi import APIRouter
from datetime import datetime

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("/")
async def health_check():
    """Simple health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "bioinfo-api"
    }
    
@router.get("/detailed")
async def detailed_health():
    """Detailed health check w/ system info."""
    import sys
    import os
    
    return {
        "status": "healthy",
        "python_version": sys.version,
        "platform": sys.platform,
        "environment": os.getenv("ENVIRONMENT", "development"),
        "timestamp": datetime.now().isoformat(),
        "service": "bioinfo-api"
    }