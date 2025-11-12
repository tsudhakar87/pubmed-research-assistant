# PubMed Research Assistant
**_This project is a work-in-progress!_**

A comprehensive bioinformatics research platform that automates literature searches, provides semantic analysis, and offers data analytics for scientific research. Built with FastAPI, React, and integrated with Google Cloud services and NCBI APIs.

## Overview

This project enables researchers to:
- Search and retrieve scientific articles from PubMed/NCBI databases
- Perform semantic analysis on research literature using AI embeddings
- Analyze publication trends and generate statistical insights
- Deploy scalable research APIs to Google Cloud Run
- Integrate with Claude Desktop via MCP (Model Context Protocol) servers

## Architecture

```
pubmed-research-assistant/
├── bioinfo-backend/          # FastAPI backend server
│   ├── src/
│   │   ├── api/             # REST API routes
│   │   ├── external/        # External API clients (NCBI)
│   │   ├── config/          # Configuration and settings
│   │   ├── models/          # Data models
│   │   └── services/        # Business logic services
│   ├── mcp_servers/         # MCP servers for Claude Desktop
│   │   ├── ncbi_server.py   # PubMed search tools
│   │   ├── vector_server.py # Semantic search & embeddings
│   │   └── analytics_server.py # Data analysis tools
│   ├── Dockerfile           # Container configuration
│   ├── cloudbuild.yaml      # Google Cloud Build config
│   └── deploy.sh            # Deployment automation script
│
├── bioinfo-frontend/        # React frontend application
│   └── [React app structure]
│
├── .env                     # Environment configuration
└── README.md               # This file
```

## Components

### Backend API (bioinfo-backend)

FastAPI-based REST API providing:
- **NCBI/PubMed Integration**: Search and fetch scientific articles
- **Rate Limiting**: Compliant with NCBI API usage policies
- **Data Parsing**: XML response parsing into structured data
- **Health Checks**: API monitoring endpoints

**Tech Stack:**
- FastAPI for REST APIs
- aiohttp for async HTTP requests
- Pydantic for data validation
- Gunicorn + Uvicorn for production serving

### MCP Servers

MCP (Model Context Protocol) servers enable Claude Desktop to access research tools:

1. **NCBI Server** - PubMed article search and retrieval
2. **Vector Server** - Semantic search using Google Vertex AI embeddings and ChromaDB
3. **Analytics Server** - Publication trend analysis and BigQuery integration

These run locally and communicate with Claude Desktop via stdio.

### Frontend (bioinfo-frontend)
**In progress!**
React-based web interface for:
- Article search and browsing
- Research workflow management
- Results visualization

## Prerequisites

### Required
- Python 3.11 or higher
- Node.js 18+ and npm (for frontend)
- Google Cloud account (for deployment and AI features)
- NCBI E-utilities account (free registration)

### Optional
- Docker (for containerized deployment)
- Claude Desktop (for MCP server integration)

## Setup

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/pubmed-research-assistant.git
cd pubmed-research-assistant
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory:

```bash
# Google Cloud
PROJECT_ID=your-gcp-project-id

# NCBI E-utilities (required)
NCBI_EMAIL=your-email@example.com
NCBI_API_KEY=your-optional-api-key

# Optional: Frontend origin for CORS
CORS_ORIGINS=http://localhost:5173
```

Get an NCBI API key: https://www.ncbi.nlm.nih.gov/account/settings/

### 3. Backend Setup

```bash
cd bioinfo-backend

# Create virtual environment
python -m venv .bioinfo-venv
source .bioinfo-venv/bin/activate  # On Windows: .bioinfo-venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run development server
python run.py
```

The API will be available at:
- API: http://localhost:8080
- Docs: http://localhost:8080/docs
- Health: http://localhost:8080/api/v1/health

### 4. Frontend Setup

```bash
cd bioinfo-frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will be available at http://localhost:5173

## Development

### Running Backend Locally

Two options:

**Option 1: Development server with hot reload**
```bash
cd bioinfo-backend
python run.py
```

**Option 2: Direct uvicorn**
```bash
cd bioinfo-backend
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8080
```

### Testing API Endpoints

```bash
# Health check
curl http://localhost:8080/api/v1/health

# Search PubMed (example)
curl -X POST http://localhost:8080/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "CRISPR gene editing", "max_results": 5}'
```

### MCP Server Development

MCP servers are designed for local use with Claude Desktop. To test:

```bash
cd bioinfo-backend

# Test NCBI server
export NCBI_EMAIL="your-email@example.com"
./mcp_servers/start_ncbi_server.sh
```

See `bioinfo-backend/mcp_servers/README.md` for detailed MCP setup instructions.

## Deployment

### Deploy to Google Cloud Run

**Quick deployment:**

```bash
cd bioinfo-backend
export PROJECT_ID=your-gcp-project-id
./deploy.sh
```

This automated script will:
1. Enable required Google Cloud APIs
2. Create Artifact Registry repository
3. Configure permissions
4. Build Docker image
5. Deploy to Cloud Run

**Manual deployment:**

```bash
# Enable required APIs
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    artifactregistry.googleapis.com

# Deploy using Cloud Build
gcloud builds submit --config=cloudbuild.yaml
```

See `bioinfo-backend/DEPLOYMENT.md` for comprehensive deployment documentation.

### Post-Deployment Configuration

**Set CORS for frontend:**
```bash
gcloud run services update bioinfo-backend-api \
    --region=us-central1 \
    --set-env-vars=CORS_ORIGINS=https://your-frontend-domain.com
```

**Add secrets (recommended):**
```bash
echo -n "your-email@example.com" | gcloud secrets create ncbi-email --data-file=-
echo -n "your-api-key" | gcloud secrets create ncbi-api-key --data-file=-
```

## Google Cloud APIs

Enable these APIs in your GCP project:

```bash
gcloud services enable \
    aiplatform.googleapis.com \
    run.googleapis.com \
    sqladmin.googleapis.com \
    bigquery.googleapis.com \
    storage.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com
```

## Project Structure Details

### Backend Routes

- `GET /` - API root information
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation
- `GET /api/v1/health` - Health check endpoint
- `POST /api/v1/search` - Search PubMed articles (example endpoint)

### External API Clients

**NCBI Client** (`src/external/ncbi_client.py`):
- Async HTTP client for NCBI E-utilities
- Rate limiting (3 req/sec without API key, 10 req/sec with key)
- XML parsing to structured data models
- Error handling and retries

**Data Parser** (`src/external/data_parser.py`):
- PubMed XML response parsing
- Article metadata extraction (title, abstract, authors, etc.)
- Date and keyword processing

### Configuration

Settings are managed via `src/config/settings.py` using Pydantic Settings:
- Environment-based configuration
- Type validation
- Default values for development

## Contributing

### Code Style

- Python: Follow PEP 8
- Use type hints
- Document functions with docstrings
- Format with black (if available)

### Testing

```bash
# Run backend tests
cd bioinfo-backend
pytest

# Run frontend tests
cd bioinfo-frontend
npm test
```

## Common Issues

### Backend won't start
- Check that port 8080 is not in use: `lsof -i :8080`
- Verify Python version: `python --version` (must be 3.11+)
- Check environment variables are set correctly

### NCBI API errors
- Verify NCBI_EMAIL is set and valid
- Check rate limiting (max 3 requests/second without API key)
- Ensure internet connection is stable

### Docker build fails
- Check that .dockerignore excludes virtual environments
- Verify requirements.txt includes all dependencies
- Try building locally: `docker build -t test-image .`

### MCP servers not working with Claude Desktop
- Ensure startup scripts have execute permissions: `chmod +x mcp_servers/start_*.sh`
- Check that scripts redirect output to stderr (`>&2`)
- Verify Claude Desktop config path is absolute, not relative

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [NCBI E-utilities API](https://www.ncbi.nlm.nih.gov/books/NBK25501/)
- [Google Cloud Run Documentation](https://cloud.google.com/run/docs)
- [MCP Protocol Specification](https://modelcontextprotocol.io)
- [ChromaDB Documentation](https://docs.trychroma.com/)

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review `bioinfo-backend/DEPLOYMENT.md` for deployment issues
3. Review `bioinfo-backend/mcp_servers/README.md` for MCP issues
4. Open an issue in the repository

## Acknowledgments

- NCBI for providing the E-utilities API
- Anthropic for the MCP protocol and Claude integration
- Google Cloud Platform for infrastructure services
