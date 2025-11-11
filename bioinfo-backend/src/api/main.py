# FastAPI application for backend
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# routes
from .routes import health, query

app = FastAPI(
    title="NCBI research assistant",
    description="API for NCBI research assistant",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # frontend dev server
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
