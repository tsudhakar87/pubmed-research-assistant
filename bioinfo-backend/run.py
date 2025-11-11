"""development server for FastAPI app"""

import uvicorn
import os
from pathlib import Path
from src.config.settings import settings

def main():
    os.chdir(Path(__file__).parent)
    
    print("---------- !!! API started !!! ----------")
    print(f"starting ncbi research assistant API...")
    print(f"environment: {settings.environment}")
    print(f"URL: http://{settings.api_host}:{settings.api_port}")
    print(f"API Docs: http://{settings.api_host}:{settings.api_port}/docs")
    print("------------------------------------------")
    
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,  # hot reload for development
        log_level="debug" if settings.debug else "info",
        reload_dirs=["src"], 
    )

if __name__ == "__main__":
    main()