# PubMed Research Assistant

A research platform for searching PubMed, bioRxiv, and medRxiv literature, ranking results by semantic relevance, and synthesizing findings with Gemini AI. The backend is built with FastAPI, the frontend with React, and the project is deployed on Google Cloud Run.

**Live demo:** [pubmed-assistant.web.app](https://pubmed-assistant.web.app)

## Architecture

```
pubmed-research-assistant/
├── bioinfo-backend/
│   ├── src/
│   │   ├── api/routes/       # REST endpoints + WebSocket
│   │   ├── agents/           # Query classifier, synthesizer, evidence extractor
│   │   ├── external/         # NCBI client, bioRxiv/medRxiv client, rate limiter, data parser
│   │   ├── services/         # Auth, Cloud SQL, BigQuery, Vertex AI
│   │   ├── models/           # ORM models (SQLAlchemy 2.0) + request/response schemas
│   │   ├── utils/            # Error handlers, logging, variant detection
│   │   └── config/           # Settings, Vertex AI config
│   ├── alembic/              # DB migrations
│   ├── tests/                # pytest suite (188 tests)
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
| AI | Vertex AI gemini-3.8-flash (synthesis + evidence extraction), text-embedding-004 (relevance ranking) |
| Database | PostgreSQL (local dev) → Cloud SQL (prod) |
| Analytics | BigQuery (time-partitioned query events table) |
| Frontend | React 19, TypeScript, Vite, react-router-dom, Roboto/Roboto Mono fonts |
| Deployment | Google Cloud Run, Cloud Build, Artifact Registry |
| CI | GitHub Actions (pytest + ruff + tsc + vite build) |

## API Endpoints

### Auth
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/auth/google` | Exchange Google ID token for JWT |
| `GET` | `/api/v1/auth/me` | Get current user info |
| `DELETE` | `/api/v1/auth/history` | Clear all query history for current user |
| `DELETE` | `/api/v1/auth/account` | Delete account and all associated data |

### Query
| Method | Path | Description |
|---|---|---|
| `WS` | `/api/v1/ws/query` | Streaming research pipeline (auth via first message) |
| `GET` | `/api/v1/query/history` | Past queries for current user |
| `GET` | `/api/v1/query/history/{query_id}` | Reopen cached result |
| `GET` | `/api/v1/query/similar?q=...` | Semantically similar past queries |
| `POST` | `/api/v1/query/{id}/synthesize` | Re-run Gemini synthesis on demand |

### Papers
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/papers/{pmid}` | Paper detail + variant detection |
| `POST` | `/api/v1/papers/compare` | AI-powered diff of 2-3 papers |
| `GET` | `/api/v1/trends` | Publication trend counts (longitudinal, via PubMed ESearch) |

### Health
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Service health (DB, Vertex AI status) |

### WebSocket pipeline events

The pipeline emits these events in order:

```
classifying → searching_pubmed → searching_preprints → retrieving_abstracts
  → scoring_relevance → papers_ready → extracting_evidence → synthesizing → done | error
```

**Pipeline details:**
- `searching_pubmed` and `searching_preprints` (bioRxiv + medRxiv) run in parallel
- Deduplication is DOI-first
- `scoring_relevance` ranks results by cosine similarity against the query embedding (Vertex AI text-embedding-004)
- `extracting_evidence` runs per-paper structured extraction (study design, population, effect size, stance) via Gemini, with iCite citation data integrated and population-weighted stance aggregation

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
GOOGLE_CLOUD_PROJECT=<gcp-project-id>
VERTEX_AI_LOCATION=us-central1
VERTEX_AI_MODEL=gemini-3.8-flash
VERTEX_AI_EMBEDDING_MODEL=text-embedding-004

# Auth
GOOGLE_CLIENT_ID=your_oauth_client_id.apps.googleusercontent.com
JWT_SECRET=change_me_in_prod        # openssl rand -hex 32

# Database (local)
DATABASE_URL=postgresql+asyncpg://YOUR_MACOS_USER@localhost:5432/bioinfo_db

# BigQuery (optional for analytics, fails silently if unset)
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
pytest                      # 188 tests
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
echo -n "$JWT_SECRET" | gcloud secrets create jwt-secret --data-file=-
```

### Deploy

```bash
cd bioinfo-backend
export PROJECT_ID=<gcp-project-id>
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
```

**Migrations** run automatically via a Cloud Run Job defined in `cloudbuild.yaml` on each deploy — no manual proxy step needed.

## CI

GitHub Actions runs on every push/PR to `main`:

- **backend-test** — pytest (188 tests, no DB needed)
- **backend-lint** — ruff (E, F, W rules)
- **frontend-build** — tsc --noEmit + vite build

## Common Issues

**`role "postgres" does not exist`** — Use your macOS username as the Postgres user in `DATABASE_URL`.

**`ModuleNotFoundError: asyncpg`** — `pip install asyncpg --force-reinstall`

**WebSocket auth fails** — Send JWT in the first message body, not as a header (browsers don't support custom WS headers).

## Resources

- [FastAPI docs](https://fastapi.tiangolo.com/)
- [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/)
- [Vertex AI Gemini](https://cloud.google.com/vertex-ai/generative-ai/docs)
- [Cloud Run](https://cloud.google.com/run/docs)
