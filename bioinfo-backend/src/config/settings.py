from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional, List
import os

class Settings(BaseSettings):
    # Environment
    environment: str = "development"
    debug: bool = True

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8080

    # CORS - Allow multiple origins. `CORS_ORIGINS` itself is read separately in
    # main.py as a plain comma-separated string, so this default list is bound to
    # a different env var name to avoid pydantic-settings trying to JSON-parse
    # CORS_ORIGINS as a list (which crashes on a plain comma-separated value).
    cors_origins: List[str] = Field(
        default=[
            "http://localhost:5173",  # Frontend dev server
            "http://localhost:3000",  # Alternative frontend port
        ],
        validation_alias="CORS_ORIGINS_DEFAULT",
    )
    
    # Google Cloud
    project_id: str = os.getenv("PROJECT_ID")
    region: str = "us-central1"
    
    # Database
    database_url: Optional[str] = None
    bigquery_dataset: str = "bioinfo_analytics"

    # NCBI E-utilities
    ncbi_email: str = os.getenv("NCBI_EMAIL", "your-email@example.com")
    ncbi_api_key: Optional[str] = os.getenv("NCBI_API_KEY")
    ncbi_tool_name: str = "bioinformatics-research-assistant"

    class Config:
        env_file = ".env"

# Global settings instance
settings = Settings()