# FastAPI application for backend
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

# routes
from .routes import health, query
from ..config.settings import settings

app = FastAPI(
    title="NCBI Research Assistant",
    description="API for NCBI research assistant with PubMed search, semantic analysis, and data analytics",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS origins
# In production, add your frontend domain to CORS_ORIGINS env var
cors_origins = settings.cors_origins.copy()

# Allow additional origins from environment variable
additional_origins = os.getenv("CORS_ORIGINS", "")
if additional_origins:
    cors_origins.extend(additional_origins.split(","))

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# include routers in app
app.include_router(health.router, prefix="/api/v1")
app.include_router(query.router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "message": "NCBI research assistant API",
        "status": "running",
        "docs": "/docs",
        "health": "/api/v1/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080, reload=True)
