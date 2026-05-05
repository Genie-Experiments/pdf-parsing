# pdf-parser-backend

FastAPI REST API + ARQ async worker for the PDF Parser. Handles job lifecycle, live log streaming via SSE, and object storage. The pipeline itself lives in `../pipeline`.

## Structure

```
backend/
├── main.py                 FastAPI app + lifespan (DB init, MinIO bucket)
├── api/
│   ├── deps.py             Shared dependencies (DB session, auth)
│   └── routes/jobs.py      All job endpoints
├── core/
│   ├── config.py           Pydantic Settings (reads .env)
│   ├── database.py         Async SQLAlchemy engine + session factory
│   └── storage.py          MinIO client wrapper
├── models/
│   └── job.py              Job SQLModel table + response schemas
├── worker/
│   ├── tasks.py            ARQ task definitions + WorkerSettings
│   └── pipeline.py         Thin wrapper — calls pipeline steps + streams logs
└── alembic/                DB migration scripts
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/jobs` | Upload PDF → create job → enqueue pipeline task |
| `GET` | `/api/v1/jobs` | List user's jobs (paginated: `?limit=50&offset=0`) |
| `GET` | `/api/v1/jobs/{id}` | Get job status |
| `GET` | `/api/v1/jobs/{id}/logs` | SSE stream of live pipeline logs |
| `GET` | `/api/v1/jobs/{id}/result` | Markdown text + presigned PDF URL |
| `GET` | `/api/v1/jobs/{id}/segments` | Dolphin JSON (bounding boxes for PDF overlay) |
| `DELETE` | `/api/v1/jobs/{id}` | Delete a job record |
| `GET` | `/api/v1/auth/login` | Initiate Google OAuth2 login |
| `GET` | `/api/v1/auth/me` | Return current user email |
| `POST` | `/api/v1/auth/logout` | Clear session cookie |
| `GET` | `/health` | Health check |

Interactive docs: http://localhost:8000/docs

---

## Quick Start

### 1. Start infrastructure (Postgres, Redis, MinIO)

```bash
# From repo root
docker compose up postgres redis minio -d
```

### 2. Install backend deps

```bash
cd backend
uv sync
```

### 3. Configure

```bash
cp .env.example .env
```

Edit `.env` — key variables for local dev:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEV_BYPASS_AUTH` | `false` | Skip Google OAuth entirely — set `true` for local dev |
| `BYPASS_QUOTA` | `false` | Skip page quota enforcement — set `true` for local dev |
| `DATABASE_URL` | `postgresql+asyncpg://pdf:pdf@localhost:5432/pdf_parser` | Postgres connection |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `MINIO_ENDPOINT` | `localhost:9000` | MinIO host:port |
| `SECRET_KEY` | — | JWT signing key (change in production) |
| `OPENAI_API_KEY` | — | Required only if LLM pipeline processing is enabled |

For local dev, set both bypass flags:
```
DEV_BYPASS_AUTH=true
BYPASS_QUOTA=true
```

### 4. Run DB migrations

```bash
cd backend
uv run alembic upgrade head
```

### 5. Start API server (Terminal 1)

```bash
cd backend
uv run uvicorn main:app --reload --port 8000
```

### 6. Start worker (Terminal 2)

```bash
cd backend
uv sync --extra ml    # first time only — installs torch (~2 GB)
uv run python -m arq worker.tasks.WorkerSettings
```

---

## End-to-End Test (curl)

`DEV_BYPASS_AUTH=true` authenticates all requests as `dev@example.com`. Run with three terminals (API, worker, curl).

**Health check**
```bash
curl -s http://localhost:8000/health | jq
# → {"status":"ok"}
```

**Submit a job — single page**
```bash
JOB=$(curl -s -X POST http://localhost:8000/api/v1/jobs \
  -F "file=@../sample_data/sample.pdf" \
  -F "page=5" \
  -F "segments_to_refine=code,fig,tab")
echo $JOB | jq
JOB_ID=$(echo $JOB | jq -r '.id')
echo "Job ID: $JOB_ID"
# → {status: "queued", page: 5, ...}
```

**Submit a full PDF** (omit `page` and `segments_to_refine` for defaults)
```bash
JOB=$(curl -s -X POST http://localhost:8000/api/v1/jobs \
  -F "file=@../sample_data/sample.pdf")
JOB_ID=$(echo $JOB | jq -r '.id')
```

**Check job status**
```bash
curl -s http://localhost:8000/api/v1/jobs/$JOB_ID | jq '.status'
# → "queued" → "running" → "done"
```

**Stream live pipeline logs (SSE — blocks until job completes)**
```bash
curl -N http://localhost:8000/api/v1/jobs/$JOB_ID/logs
# → data: STEP 1: Processing PDF with Dolphin model
# → data: ...
# → data: __DONE__
```

**Get result (once status is "done")**
```bash
curl -s http://localhost:8000/api/v1/jobs/$JOB_ID/result | \
  jq '{pdf_url: .pdf_url, preview: .markdown[:300]}'
```

**Get Dolphin bounding-box segments**
```bash
curl -s http://localhost:8000/api/v1/jobs/$JOB_ID/segments | jq 'length'
# → number of detected segments
```

**List all jobs**
```bash
curl -s "http://localhost:8000/api/v1/jobs?limit=10" | \
  jq '[.[] | {id, filename, status, page}]'
```

**Delete a job**
```bash
curl -s -X DELETE http://localhost:8000/api/v1/jobs/$JOB_ID -o /dev/null -w "%{http_code}"
# → 204
```

---

## Run with Docker

Build context is the repo root (worker needs `../pipeline`):

```bash
# From repo root
docker compose up api worker --build
```

Or include the frontend:
```bash
docker compose --profile frontend up --build
```

---

## Database Migrations

```bash
# From backend/

# Apply all pending migrations
uv run alembic upgrade head

# Generate a new migration after model changes
uv run alembic revision --autogenerate -m "description"
```

---

## Job Lifecycle

```
POST /jobs
  → PDF uploaded to MinIO (key: jobs/{id}/input/{filename})
  → Job row inserted (status=queued)
  → ARQ task enqueued in Redis

Worker: run_pipeline(job_id)
  → downloads PDF from MinIO
  → runs 10-step pipeline in a temp dir
  → each log line published to Redis pub/sub → SSE → browser
  → uploads markdown + Dolphin JSON to MinIO
  → updates Job row (status=done)

GET /jobs/{id}/result
  → returns { markdown: "...", pdf_url: "<presigned MinIO URL>" }
```
