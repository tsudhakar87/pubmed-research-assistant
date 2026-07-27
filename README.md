# PubMed Research Assistant

A bioinformatics research platform for searching PubMed literature, detecting genetic variants, scoring them with NVIDIA BioNeMo, and synthesizing findings with Gemini AI. Built with FastAPI + React, deployed on Google Cloud Run.

## Architecture

```
pubmed-research-assistant/
├── bioinfo-backend/
│   ├── src/
│   │   ├── api/routes/       # REST endpoints + WebSocket
│   │   ├── agents/           # Query classifier, synthesizer, bioinfo agent
│   │   ├── external/         # NCBI client, rate limiter, data parser
│   │   ├── services/         # Auth, Cloud SQL, BigQuery, Vertex AI
│   │   ├── models/           # ORM models (SQLAlchemy 2.0) + request/response schemas
│   │   ├── utils/            # Error handlers, logging, variant detection
│   │   └── config/           # Settings, Vertex AI config
│   ├── mcp_servers/          # MCP servers for Claude Desktop
│   ├── alembic/              # DB migrations
│   ├── tests/                # pytest suite (22 tests)
│   ├── Dockerfile
│   └── deploy.sh
│
├── bioinfo-frontend/
│   └── src/
│       ├── pages/            # Login, Home, History, PaperDetail, Compare
│       ├── components/       # Header, PaperCard, PipelineSteps, modals, skeletons
│       ├── services/         # api.ts (REST), websocket.ts
│       ├── hooks/            # useWebSocket, useQuery
│       └── contexts/         # AuthContext (JWT)
│
├── .github/workflows/ci.yml  # GitHub Actions CI
└── .env                      # Environment config (see below)
```

### Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.0 + asyncpg, Alembic |
| Auth | Google OAuth 2.0 ID tokens → internal JWT (HS256, 24h) |
| AI | Vertex AI Gemini 2.5 Pro (synthesis), text-embedding-004 (similarity) |
| Variant scoring | NVIDIA BioNeMo Evo2-40b via NIM API |
| Database | PostgreSQL (local dev) → Cloud SQL (prod) |
| Analytics | BigQuery (time-partitioned query events table) |
| Frontend | React 19, TypeScript, Vite, react-router-dom |
| Deployment | Google Cloud Run, Cloud Build, Artifact Registry |
| CI | GitHub Actions (pytest + ruff + tsc + vite build) |

## API Endpoints

### Auth
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/auth/google` | Exchange Google ID token for JWT |
| `GET` | `/api/v1/auth/me` | Get current user info |

### Query
| Method | Path | Description |
|---|---|---|
| `WS` | `/api/v1/ws/query` | Streaming research pipeline (auth via first message) |
| `GET` | `/api/v1/query/history` | Past queries for current user |
| `GET` | `/api/v1/query/history/{query_id}` | Reopen cached result |
| `GET` | `/api/v1/query/similar?q=...` | Semantically similar past queries |

### Papers
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/papers/{pmid}` | Paper detail + variant detection |
| `POST` | `/api/v1/papers/compare` | AI-powered diff of 2-3 papers |
| `GET` | `/api/v1/papers/{pmid}/score-variant?variant=V600E` | BioNeMo variant scoring |

### Health
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Service health (DB, Vertex AI status) |

### WebSocket pipeline events
```
classifying → searching_pubmed → retrieving_abstracts → synthesizing → done | error
```
Authenticate by sending `{"token": "<jwt>", "query": "..."}` as the first message.

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL running locally
- Google Cloud credentials (`gcloud auth application-default login`)

### 1. Environment variables

Copy and fill in `.env` at the repo root:

```bash
# NCBI
NCBI_EMAIL=you@example.com
NCBI_API_KEY=your_ncbi_key          # optional but raises rate limit to 10 rps

# Google Cloud
GOOGLE_CLOUD_PROJECT=mcp-project-476900
VERTEX_AI_LOCATION=us-central1
VERTEX_AI_MODEL=gemini-2.5-pro
VERTEX_AI_EMBEDDING_MODEL=text-embedding-004

# Auth
GOOGLE_CLIENT_ID=your_oauth_client_id.apps.googleusercontent.com
JWT_SECRET=change_me_in_prod        # openssl rand -hex 32

# Database (local)
DATABASE_URL=postgresql+asyncpg://YOUR_MACOS_USER@localhost:5432/bioinfo_db

# NVIDIA BioNeMo (add your own key)
NVIDIA_API_KEY=

# BigQuery (optional — analytics, fails silently if unset)
BIGQUERY_DATASET=pubmed_analytics
BIGQUERY_TABLE=query_events
```

### 2. Database setup

```bash
# Create local database
createdb bioinfo_db

# Run migrations
cd bioinfo-backend
alembic upgrade head
```

### 3. Backend

```bash
cd bioinfo-backend
pip install -r requirements.txt
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8080
```

Interactive docs: http://localhost:8080/docs

### 4. Frontend

```bash
cd bioinfo-frontend
# Set your Google OAuth client ID
echo "VITE_GOOGLE_CLIENT_ID=your_client_id" >> .env
npm install
npm run dev
```

App: http://localhost:5173

### 5. Tests

```bash
cd bioinfo-backend
pytest                      # 22 tests
pytest --tb=short -q        # quiet mode
```

## Deployment (Google Cloud Run)

### First-time GCP setup

```bash
# Enable APIs
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  sqladmin.googleapis.com \
  bigquery.googleapis.com \
  aiplatform.googleapis.com \
  secretmanager.googleapis.com

# Store secrets
echo -n "$JWT_SECRET"     | gcloud secrets create jwt-secret --data-file=-
echo -n "$NVIDIA_API_KEY" | gcloud secrets create nvidia-api-key --data-file=-
```

### Deploy

```bash
cd bioinfo-backend
export PROJECT_ID=mcp-project-476900
./deploy.sh
```

The script builds via Cloud Build, pushes to Artifact Registry, and deploys to Cloud Run in `us-central1`.

### Cloud SQL (prod database)

```bash
# Create instance
gcloud sql instances create bioinfo-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1

# Create database
gcloud sql databases create bioinfo_db --instance=bioinfo-db

# Run migrations against Cloud SQL (via proxy)
cloud_sql_proxy mcp-project-476900:us-central1:bioinfo-db &
DATABASE_URL="postgresql+asyncpg://USER:PASS@127.0.0.1:5432/bioinfo_db" \
  alembic upgrade head
```

## MCP Servers (Claude Desktop)

Three MCP servers expose tools to Claude Desktop:

| Server | Script | Tools |
|---|---|---|
| NCBI | `start_ncbi_server.sh` | search_pubmed, get_abstract |
| BioNeMo | `start_bionemo_server.sh` | score_variant, detect_variants_in_text |
| Vector | `start_vector_server.sh` | semantic_search |

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ncbi": {
      "command": "/absolute/path/bioinfo-backend/mcp_servers/start_ncbi_server.sh"
    },
    "bionemo": {
      "command": "/absolute/path/bioinfo-backend/mcp_servers/start_bionemo_server.sh"
    }
  }
}
```

## CI

GitHub Actions runs on every push/PR to `main`:

- **backend-test** — pytest (22 tests, no DB needed)
- **backend-lint** — ruff (E, F, W rules)
- **frontend-build** — tsc --noEmit + vite build

## Common Issues

**`role "postgres" does not exist`** — Use your macOS username as the Postgres user in `DATABASE_URL`.

**`ModuleNotFoundError: asyncpg`** — `pip install asyncpg --force-reinstall`

**WebSocket auth fails** — Send JWT in the first message body, not as a header (browsers don't support custom WS headers).

**BioNeMo returns 401** — Set `NVIDIA_API_KEY` in `.env`.

**Variant gene not detected** — Gene must appear within ~60 characters before the variant notation (e.g., `BRAF V600E`).

## Resources

- [FastAPI docs](https://fastapi.tiangolo.com/)
- [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/)
- [NVIDIA NIM (BioNeMo)](https://build.nvidia.com/)
- [Vertex AI Gemini](https://cloud.google.com/vertex-ai/generative-ai/docs)
- [Cloud Run](https://cloud.google.com/run/docs)
- [MCP Protocol](https://modelcontextprotocol.io)
