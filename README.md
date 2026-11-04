# PubMed Research Assistant

Ask a biomedical question and get more than a list of papers: the app searches PubMed, bioRxiv and medRxiv, reads each abstract, and shows **where the evidence actually points**. You see how many studies support, contradict or find no effect, in humans versus animals, how that changed over time, and what is missing. The AI summary cites every claim back to a numbered paper.

Built with FastAPI and React, deployed on Google Cloud Run, Cloud SQL and Firebase Hosting.

**Live demo:** [pubmed-assistant.web.app](https://pubmed-assistant.web.app)

![Evidence panel and cited AI synthesis](docs/images/evidence-overview.png)
<sub>Screenshot with sample data.</sub>

## Features

- **Evidence map.** Each abstract is turned into structured data: study design, organism, sample size, and whether the result supports the question. The page shows the stance breakdown (filterable to human, animal or in vitro studies), a study-design summary, and automatically detected gaps such as "no randomized trials since 2019" or "human and animal studies disagree".
- **Findings timeline.** One dot per paper, placed by year and finding, colored by organism and sized by sample size. Click a dot to jump to the paper.
- **Grounded, cited synthesis.** Gemini writes from the extracted table and the computed counts, not from raw abstracts, and cites papers as `[n]`. Citations are clickable and checked against the real paper list.
- **Verifiable findings.** Every extracted finding comes with a verbatim quote from the abstract. Quotes that can't be found word for word are flagged "not verified".
- **PubMed plus preprints.** bioRxiv and medRxiv are searched in parallel with PubMed. Preprints already published in PubMed are removed (DOI first, then normalized title) and the rest are badged as not peer reviewed.
- **Semantic relevance ranking** with Vertex AI text embeddings, shown as a "% match" on each paper, plus a "strongest evidence" sort (design, then sample size, then citation influence).
- **Citation context** from NIH iCite: citation counts and Relative Citation Ratio on every PubMed paper.
- **Live pipeline progress** over a WebSocket, query history with cached results, side-by-side paper comparison, and an account menu (sign out, clear history, delete account).
- **Variant detection** in abstracts with optional NVIDIA BioNeMo Evo2 scoring. Scoring needs nucleotide sequence context, which abstracts don't contain, so it is disabled unless that context is supplied.

![Findings timeline and paper cards](docs/images/timeline-and-cards.png)
<sub>Screenshot with sample data.</sub>

## How the evidence map works

```mermaid
flowchart LR
    Q[Query] --> C[Classify]
    C --> S1[PubMed]
    C --> S2[bioRxiv / medRxiv<br/>via Europe PMC]
    S1 --> M[Merge + dedupe]
    S2 --> M
    M --> R[Rank by<br/>embeddings]
    R --> E[Extract evidence<br/>Gemini, batched]
    R --> I[iCite citations]
    E --> A[Aggregate<br/>in code]
    I --> A
    A --> Y[Cited synthesis]
    Y --> UI[Panel, timeline,<br/>cards]
```

The design choices that keep the numbers trustworthy:

1. **Curated metadata before the model.** Study design comes from NLM's PubMed publication types (RCT, meta-analysis, review) and organism from MeSH tags (Humans, Animals, cell lines), then NIH iCite. Gemini only fills in what isn't tagged: sample size, the finding, and stance. Each label records its source, and the UI marks AI-derived labels.
2. **An explicit question.** The query is first rewritten as a yes/no question ("Does metformin affect the gut microbiome?") and shown as "Measured against", so "supports" has a clear meaning. Topic searches with no single question ("CRISPR off-target rates") skip stance and group by design instead.
3. **Quote verification.** The model must copy the sentence that states each result. The backend checks it appears in the abstract (ignoring case, spacing and quote style) and flags it if not.
4. **All counts in code.** Stance and design counts, the largest study, the latest trial, and gap statements are computed deterministically. The synthesis prompt is given these numbers and told not to recount.
5. **Rules where the model was wrong.** Testing on real data showed Gemini labeling narrative reviews as "supports". Narrative reviews are now forced to "doesn't test the question" in code; systematic reviews and meta-analyses keep their stance because they pool data.

On a real query ("metformin gut microbiome", 20 PubMed results) all 10 extracted findings had verified quotes. That is a small sample, not an accuracy benchmark. The design rationale and rollout plan are in [docs/plans/evidence-map.md](docs/plans/evidence-map.md).

**Known limitations**

- Abstracts only. Full text would add doses and effect sizes but is only freely available for open-access papers.
- PubMed's relevance ranking returns many narrative reviews; they are shown but don't count toward stance.
- Preprint search can match terms anywhere in a preprint's text, so a few off-topic preprints appear. Relevance ranking pushes them to the bottom.
- Evidence extraction adds roughly 5 to 10 seconds per search (2 to 4 extra Gemini calls, up to 30 papers).

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.0 + asyncpg, Alembic, aiohttp |
| AI | Gemini on Vertex AI via `google-genai` (structured JSON output), `text-embedding-004` |
| Literature sources | NCBI E-utilities (PubMed), Europe PMC (bioRxiv, medRxiv), NIH iCite |
| Variant scoring | NVIDIA BioNeMo Evo2 via NIM API |
| Auth | Google Identity Services ID token → app JWT (HS256, 24h) |
| Database | PostgreSQL locally, Cloud SQL in production |
| Analytics | BigQuery (query events) |
| Frontend | React 19, TypeScript, Vite, Recharts |
| Deployment | Cloud Run + Cloud Build (backend), Firebase Hosting (frontend) |
| CI | GitHub Actions: pytest, ruff, `tsc -b`, Vite build |

## Project structure

```
pubmed-research-assistant/
├── bioinfo-backend/
│   ├── src/
│   │   ├── agents/       # Pipeline orchestrator, query classifier, cited synthesis
│   │   ├── api/routes/   # REST endpoints + WebSocket
│   │   ├── external/     # PubMed, Europe PMC preprint and iCite clients; XML parser
│   │   ├── services/     # Gemini, embeddings, evidence extraction + aggregation,
│   │   │                 # query storage, auth, Cloud SQL, BigQuery
│   │   ├── models/       # SQLAlchemy models, request/response schemas
│   │   └── utils/        # Study design rules, embeddings math, variant detection
│   ├── scripts/          # phase0_check.py: test the pipeline against real APIs
│   ├── tests/            # pytest (fixtures include real PubMed/iCite responses)
│   ├── alembic/          # Database migrations
│   └── mcp_servers/      # MCP servers for Claude Desktop
├── bioinfo-frontend/
│   └── src/
│       ├── pages/        # Login, Home, History, Paper detail, Compare
│       ├── components/   # EvidencePanel, FindingsTimeline, PaperCard, AISynthesis, UserMenu, ...
│       ├── services/     # REST and WebSocket clients
│       └── contexts/     # Auth
└── docs/plans/           # Feature design docs
```

## API

| Method | Path | Description |
|---|---|---|
| `WS` | `/api/v1/ws/query` | Streaming research pipeline (send the JWT in the first message) |
| `POST` | `/api/v1/query/research` | Same pipeline as a single request |
| `GET` | `/api/v1/query/history` | The user's past queries |
| `GET` | `/api/v1/query/history/{query_id}` | Reopen a cached result |
| `POST` | `/api/v1/query/{query_id}/synthesize` | Regenerate the AI synthesis |
| `GET` | `/api/v1/query/similar?q=...` | Semantically similar past queries |
| `GET` | `/api/v1/trends?q=...&years=10` | Yearly PubMed publication counts |
| `GET` | `/api/v1/papers/{pmid}` | Paper detail with variant detection |
| `POST` | `/api/v1/papers/compare` | AI comparison of 2 or 3 papers |
| `GET` | `/api/v1/papers/{pmid}/score-variant` | BioNeMo variant scoring |
| `POST` | `/api/v1/auth/google` | Exchange a Google ID token for a JWT |
| `GET` | `/api/v1/auth/me` | Current user |
| `DELETE` | `/api/v1/auth/history` | Delete all of the user's saved queries |
| `DELETE` | `/api/v1/auth/account` | Delete the user and all their data |
| `GET` | `/api/v1/health/`, `/api/v1/health/detailed` | Service health |

WebSocket events, in order (the last three only when there are results):

```
classifying → searching_pubmed → searching_preprints → retrieving_abstracts
  → scoring_relevance → extracting_evidence → synthesizing → done | error
```

Interactive docs: `http://localhost:8080/docs` when running locally.

## Local development

**Prerequisites:** Python 3.11+, Node.js 20+, PostgreSQL, and Google Cloud credentials (`gcloud auth application-default login`) for Gemini and embeddings.

### 1. Environment

Create `.env` at the repo root. The backend and Alembic both read it.

```bash
# NCBI (email is required by NCBI; an API key raises the rate limit from 3 to 10 requests/s)
NCBI_EMAIL=you@example.com
NCBI_API_KEY=

# Google Cloud / Vertex AI
GOOGLE_CLOUD_PROJECT=your-project-id
VERTEX_AI_LOCATION=us-central1
VERTEX_AI_MODEL=gemini-3.8-flash
VERTEX_AI_EMBEDDING_MODEL=text-embedding-004

# Auth
GOOGLE_CLIENT_ID=your_oauth_client_id.apps.googleusercontent.com
JWT_SECRET=change_me                # openssl rand -hex 32

# Database
DATABASE_URL=postgresql+asyncpg://YOUR_USER@localhost:5432/bioinfo_db

# Optional
NVIDIA_API_KEY=                     # BioNeMo variant scoring
BIGQUERY_DATASET=pubmed_analytics   # analytics; skipped if unavailable
BIGQUERY_TABLE=query_events
```

Without `GOOGLE_CLOUD_PROJECT`, the app still runs: results are unranked, there is no evidence map, and the AI synthesis shows as unavailable.

### 2. Database

```bash
createdb bioinfo_db
cd bioinfo-backend
alembic upgrade head
```

### 3. Backend

```bash
cd bioinfo-backend
pip install -r requirements.txt
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8080
```

### 4. Frontend

```bash
cd bioinfo-frontend
echo "VITE_GOOGLE_CLIENT_ID=your_client_id" >> .env   # VITE_API_URL / VITE_WS_URL default to localhost:8080
npm install
npm run dev
```

App: http://localhost:5173

### 5. Tests

```bash
cd bioinfo-backend
pytest -q          # 188 tests; no database or network needed
ruff check src tests scripts --select=E,F,W --ignore=E501

cd ../bioinfo-frontend
npx tsc -b && npm run build
```

### 6. Check against the real APIs

The unit tests use fixtures. To run the pipeline against live PubMed, iCite, Europe PMC and Gemini:

```bash
cd bioinfo-backend
python -m scripts.phase0_check "metformin gut microbiome"   # add --no-gemini to skip extraction
```

It saves the raw PubMed and iCite responses under `tests/fixtures/real/` and prints metadata coverage, preprint hit counts, each paper's extracted labels and the quote-verification rate.

## Deployment

**Backend (Cloud Run):**

```bash
cd bioinfo-backend
export PROJECT_ID=your-project-id
./deploy.sh
```

This builds with Cloud Build and deploys to Cloud Run in `us-central1`, with secrets (`database-url`, `jwt-secret`, `nvidia-api-key`, `ncbi-email`, `ncbi-api-key`) from Secret Manager. See [bioinfo-backend/DEPLOYMENT.md](bioinfo-backend/DEPLOYMENT.md).

**Database migrations run separately.** Run them against Cloud SQL before deploying code that needs a new column:

```bash
cloud-sql-proxy your-project-id:us-central1:bioinfo-db        # in one terminal
cd bioinfo-backend
DATABASE_URL="postgresql+asyncpg://USER:PASS@127.0.0.1:5432/bioinfo_db" alembic upgrade head
```

**Frontend (Firebase Hosting):**

```bash
cd bioinfo-frontend
VITE_API_URL=https://<cloud-run-url>/api/v1 VITE_WS_URL=wss://<cloud-run-url>/api/v1 \
  VITE_GOOGLE_CLIENT_ID=<client-id> npm run build
firebase deploy --only hosting
```

## MCP servers (Claude Desktop)

| Server | Script | Tools |
|---|---|---|
| NCBI | `start_ncbi_server.sh` | search_pubmed, fetch_article_details, get_recent_articles |
| BioNeMo | `start_bionemo_server.sh` | score_variant, detect_variants_in_text |
| Vector | `start_vector_server.sh` | Semantic search over stored articles |
| Analytics | `start_analytics_server.sh` | Query trends, statistics and topic comparison (BigQuery) |

See [bioinfo-backend/mcp_servers/README.md](bioinfo-backend/mcp_servers/README.md) and `mcp_config_example.json` for Claude Desktop configuration.

## Troubleshooting

**`alembic` fails with "Can't load plugin: sqlalchemy.dialects:driver"**: No database URL was found. Set `DATABASE_URL` in the repo-root `.env` or your shell.

**`alembic upgrade head` fails with "relation already exists"**: The tables were created by the app at startup rather than by Alembic. Run `alembic stamp 84e84cfd77a0`, then `alembic upgrade head`.

**`column "source" of relation "query_papers" does not exist`**, or results show "not saved to history": The database is missing a migration. Run `alembic upgrade head`.

**Vite: "Failed to resolve import recharts"**: Run `npm install` in `bioinfo-frontend`, then restart the dev server.

**`role "postgres" does not exist`**: Use your local Postgres user (on macOS, usually your username) in `DATABASE_URL`.

**WebSocket auth fails**: Send the JWT in the first message body. Browsers can't set custom headers on WebSocket connections.

**BioNeMo returns 401**: Set `NVIDIA_API_KEY`.

## Resources

[NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/) · [Europe PMC REST API](https://europepmc.org/RestfulWebService) · [NIH iCite API](https://icite.od.nih.gov/api) · [Vertex AI Gemini](https://cloud.google.com/vertex-ai/generative-ai/docs) · [NVIDIA NIM (BioNeMo)](https://build.nvidia.com/) · [FastAPI](https://fastapi.tiangolo.com/) · [MCP](https://modelcontextprotocol.io)
