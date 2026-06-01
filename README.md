# PDF Parser

Extracts clean Markdown from PDFs using ByteDance's [Dolphin](https://github.com/bytedance/Dolphin) model.

Two ways to use it:
1. **[Standalone CLI](#1-standalone-pipeline-cli)** — run the pipeline directly against local PDFs, no services needed
2. **[Full-stack SaaS](#2-full-stack-saas)** — web UI with real-time logs, PDF ↔ Markdown navigation, job history

## Repository Layout

```
pdf-parsing/
├── pipeline/           Core ML pipeline — installable Python package
│   ├── Dolphin/            git submodule — ByteDance layout model
│   ├── html-to-markdown/   git submodule — Go HTML→Markdown converter
│   └── README.md
├── backend/            FastAPI API + ARQ worker
│   └── README.md
├── frontend/           Next.js 16 web application
│   └── README.md
├── docker-compose.yml  Full-stack orchestration
├── Makefile            Convenience commands
└── sample_data/        Sample PDFs for testing
```

---

## 1. Standalone Pipeline CLI

No Docker, no Postgres, no Redis — just Python and the pipeline.

### One-time setup

```bash
git clone --recurse-submodules https://github.com/Genie-Experiments/pdf-parsing.git
cd pdf-parsing

# CPU / Apple Silicon
make setup-pipeline

# NVIDIA GPU (Linux/Windows)
make setup-pipeline-gpu                        # default CUDA cu124
make setup-pipeline-gpu CUDA_VERSION=cu121     # override CUDA version
```

This installs ML deps and downloads Dolphin model weights (~5 GB) into `pipeline/hf_model/`.

### Configure

```bash
cd pipeline
cp .env.example .env
# Set DATA_DIRECTORY in .env, or pass it via --data-dir
```

### Run

```bash
cd pipeline

# Process a directory of PDFs
uv run python main.py --data-dir /path/to/pdfs

# Process a single PDF
uv run python main.py --pdf-file /path/to/doc.pdf

# Process a single page (1-indexed)
uv run python main.py --pdf-file /path/to/doc.pdf --page 5

# Skip Dolphin inference, re-run post-processing only (steps 2–10)
START_FROM_STEP=2 uv run python main.py --data-dir /path/to/pdfs

# Resume a partial run — skip steps whose outputs already exist
RESUME=true uv run python main.py --data-dir /path/to/pdfs
```

### Output

```
Results/
└── <doc_name>/
    ├── recognition_json/<doc_name>.json   Dolphin layout JSON (bounding boxes)
    └── markdown/
        ├── <doc_name>.md                  Final post-processed Markdown
        └── figures/*.png                  Extracted figure images
```

For `--page N` runs, output is under `<doc_name>_page#N/`.

### Configuration reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIRECTORY` | — | Input PDF directory (required unless using `--pdf-file`) |
| `OUTPUT_DIRECTORY` | `./Results` | Output root |
| `RESUME` | `false` | Skip steps whose outputs already exist |
| `START_FROM_STEP` | `1` | Start from step N. Use `2` to skip Dolphin re-inference. |
| `PROCESS_CODE_USING_LLM` | `false` | GPT-4o Vision on code blocks |
| `PROCESS_FIGURES_USING_LLM` | `false` | GPT-4o Vision on figures |
| `OPENAI_API_KEY` | — | Required only if either LLM flag is `true` |

See [`pipeline/README.md`](pipeline/README.md) for the full reference and pipeline step details.

---

## 2. Full-stack SaaS

Upload PDFs through a browser, stream live processing logs, and navigate between PDF regions and their Markdown output interactively.

### Architecture

```
Upload PDF (POST /api/v1/jobs)
    ↓ stored in MinIO
    ↓ Job row created in Postgres (status=queued)
    ↓ task enqueued in Redis (ARQ)

ARQ Worker picks up task
    ↓ downloads PDF from MinIO
    ↓ runs 10-step pipeline
    ↓ logs streamed to Redis pub/sub → SSE → browser
    ↓ uploads markdown + Dolphin JSON back to MinIO
    ↓ updates Job row (status=done)

Frontend
    ↓ user selects PDF, configures page + segment options, submits
    ↓ step progress panel updated by polling GET /jobs/{id} every 2 s
    ↓ on done: fetches markdown + segments
    ↓ PDF rendered in canvas, hover a region → highlight matching markdown
    ↓ download extracted Markdown from the header
```

### Services

| Service | Role |
|---------|------|
| `api` | FastAPI REST API + SSE log endpoint |
| `worker` | ARQ worker — runs the ML pipeline |
| `postgres` | Job metadata |
| `redis` | Job queue + live log pub/sub |
| `minio` | Object store for PDFs and results |
| `frontend` | Next.js 16 web UI |

### Quick Start — Docker (recommended)

> **Prerequisite:** Dolphin model weights (~5 GB) must be in `pipeline/hf_model/` before starting Docker.
> Run `make model` to download them (skipped automatically if weights are already present).
> `make model` requires [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone --recurse-submodules https://github.com/Genie-Experiments/pdf-parsing.git
cd pdf-parsing
cp .env.example .env   # fill in SECRET_KEY; add OPENAI_API_KEY if needed
make model             # download Dolphin weights into pipeline/hf_model/ (skipped if already present)
make docker-up
```

| URL | Service |
|-----|---------|
| http://localhost:3000 | Frontend |
| http://localhost:8000 | API |
| http://localhost:8000/docs | Swagger UI |
| http://localhost:9001 | MinIO console |

### GPU Support (NVIDIA) — Docker

The worker image ships with CPU-only PyTorch by default. To enable GPU inference on a server with an NVIDIA card:

**1. Server prerequisites**

- NVIDIA drivers installed (`nvidia-smi` should return output)
- [`nvidia-container-toolkit`](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) installed and Docker configured:
  ```bash
  nvidia-ctk runtime configure --runtime=docker
  sudo systemctl restart docker
  ```

**2. Grant the worker container GPU access**

In `docker-compose.yml`, under the `worker` service, add a `reservations` block inside `deploy.resources`:

```yaml
worker:
  deploy:
    resources:
      limits:
        cpus: "4"
        memory: 8G
      reservations:
        devices:
          - driver: nvidia
            count: all
            capabilities: [gpu]
```

**3. Install CUDA PyTorch in the worker image**

In `backend/Dockerfile.worker`, replace the `uv sync` step with:

```dockerfile
ARG CUDA_VERSION=cu124
RUN --mount=type=cache,target=/root/.cache/uv \
    cd backend && uv sync --frozen --no-dev --no-install-project --extra ml && \
    uv pip install torch torchvision \
      --index-url https://download.pytorch.org/whl/${CUDA_VERSION} \
      --force-reinstall
```

`cu124` matches CUDA 12.4 — confirm your driver version with `nvidia-smi` and adjust if needed (`cu121`, `cu118`, etc.).

**4. Build and start**

```bash
docker compose build worker
docker compose up -d
```

> **Note:** The pipeline's standalone CLI also supports GPU — see the GPU note under [Make Commands](#make-commands).

### Local Development (Docker for Infra only)

**Prerequisites:** Python 3.12 + uv, Node.js 22+

**backend/.env** — set these for local dev to skip auth and quota:
```
DEV_BYPASS_AUTH=true   # skip Google OAuth
BYPASS_QUOTA=true      # skip page quota enforcement
```

**frontend/.env.local** — set the API URL (defaults to localhost:8000 if omitted):
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

See [`backend/README.md`](backend/README.md) and [`frontend/README.md`](frontend/README.md) for the full setup reference and API examples.

```bash
# 1. Start infrastructure (Postgres, Redis, MinIO)
make infra-up

# 2. Install all deps + download model weights
make setup

# 3. Apply DB migrations
make db-migrate

# 4. Start each service in a separate terminal
make dev-api        # FastAPI on :8000
make dev-worker     # ARQ worker (needs ML deps)
make dev-frontend   # Next.js on :3000
```

---

## User Quota Management

Each user gets a page quota on first submission (default: `DEFAULT_PAGE_QUOTA`, set in `backend/.env`). Pages are consumed at submission time; failed jobs do not refund quota.

**Set or update quota for a specific user:**

```bash
make set-quota EMAIL=user@example.com QUOTA=500
```

**Via raw SQL (if services are already running):**

```bash
docker compose exec postgres psql -U pdf -d pdf_parser \
  -c "UPDATE user_quota SET page_quota = 500 WHERE email = 'user@example.com';"
```

**Disable quota enforcement entirely (dev / internal use):**

In `backend/.env`:
```
BYPASS_QUOTA=true
```

---

## Pipeline Steps

| Step | Description |
|------|-------------|
| 1 | **Dolphin inference** — extracts baseline Markdown + layout JSON |
| 2 | **Raw text extraction** — PyMuPDF text saved as OCR reference |
| 3 | **Section hierarchy** — font metric analysis → heading level JSON |
| 4 | **Backup** — copies `.md` files before any mutation |
| 5 | **Segment refinement** — tables → Markdown, code cleanup, optional LLM |
| 6 | **Insert page breaks** — replaces `---` with `<!-- page_break_N -->` |
| 7 | **Remove headers/footers** — strips repetitive cross-page content |
| 8 | **Fix OCR errors** — fuzzy-matches Markdown against raw text |
| 9 | **Fix section hierarchy** — corrects heading levels using JSON from step 3 |
| 10 | **Standardize bullets** — converts `•`, `◦`, etc. to `-` |

## Make Commands

| Command | Description |
|---------|-------------|
| `make setup-pipeline` | Pipeline-only setup — deps + model weights (CPU / Apple Silicon) |
| `make setup-pipeline-gpu` | Pipeline-only setup with CUDA GPU support |
| `make setup` | Full setup — pipeline + backend + frontend + model weights |
| `make dev-api` | Start FastAPI dev server |
| `make dev-worker` | Start ARQ worker |
| `make dev-frontend` | Start Next.js dev server |
| `make dev-pipeline DATA_DIR=<path>` | Run pipeline CLI |
| `make format` | Auto-fix formatting (pipeline + backend) |
| `make lint` | ruff + pylint (pipeline + backend) |
| `make db-migrate` | Apply pending Alembic migrations |
| `make dev-reset` | Wipe Postgres, Redis, and MinIO volumes; restart infra; re-apply migrations |
| `make docker-up` | Build and start all Docker services |
| `make docker-down` | Stop all Docker services |
| `make clean` | Remove `__pycache__`, `.pyc`/`.pyo`, `.venv` dirs |
| `make set-quota EMAIL=<email> QUOTA=<n>` | Set page quota for a user |

> **GPU note:** CUDA is not available on Apple Silicon — use `make setup-pipeline` (MPS is included in the default PyTorch build). For NVIDIA on Linux/Windows, use `make setup-pipeline-gpu`. Confirm your CUDA version with `nvidia-smi`; default is `cu124`.

## Limitations

- Table of Contents sections are not parsed correctly.
- Complex/multi-span tables may have inaccuracies.
- Code blocks without LLM may lose indentation in edge cases.
- 4-column or unusual layouts may produce occasional OCR errors.

## Acknowledgments

- [ByteDance Dolphin](https://github.com/bytedance/Dolphin) — core document parsing model
- [html-to-markdown](https://github.com/JohannesKaufmann/html-to-markdown) — HTML table to Markdown conversion
