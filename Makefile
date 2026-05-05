.PHONY: submodules model \
        install-pipeline install-pipeline-gpu install install-dev \
        setup-pipeline setup-pipeline-gpu setup \
        clean \
        format lint typecheck check code-quality \
        infra-up infra-down db-migrate dev-reset \
        dev-api dev-worker dev-frontend dev-pipeline dev \
        certs docker-up docker-down docker-up-tls

# ── Setup ──────────────────────────────────────────────────────────────────────

submodules:
	git submodule update --init --recursive

model:
	@if [ -d pipeline/hf_model ] && [ "$$(ls -A pipeline/hf_model 2>/dev/null)" ]; then \
	  echo "Model weights already present at pipeline/hf_model/ — skipping download."; \
	else \
	  cd pipeline && uv run huggingface-cli download ByteDance/Dolphin-1.5 --local-dir ./hf_model; \
	fi

install-pipeline:
	cd pipeline && uv sync --extra ml

## NVIDIA GPU only (Linux/Windows). Adjust CUDA_VERSION for your driver (cu118, cu121, cu124).
## Not applicable on macOS — use install-pipeline instead.
CUDA_VERSION ?= cu124
install-pipeline-gpu:
	cd pipeline && uv sync --extra ml
	cd pipeline && uv pip install torch torchvision \
	  --index-url https://download.pytorch.org/whl/$(CUDA_VERSION) \
	  --force-reinstall

install:
	cd pipeline && uv sync --extra ml
	cd backend  && uv sync
	cd frontend && npm install

install-dev:
	cd pipeline && uv sync --extra ml --group dev
	cd backend  && uv sync --group dev
	cd frontend && npm install

# Pipeline-only setup — no backend/frontend deps
setup-pipeline: submodules install-pipeline model

# Pipeline-only setup with CUDA GPU support (NVIDIA Linux/Windows only).
# Override CUDA version if needed: make setup-pipeline-gpu CUDA_VERSION=cu121
setup-pipeline-gpu: submodules install-pipeline-gpu model

# Full one-time setup after cloning
setup: submodules install model

# ── Clean ──────────────────────────────────────────────────────────────────────

clean:
	find . -type d -name "__pycache__" -not -path "./.git/*" -exec rm -rf {} +
	find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -not -path "./.git/*" -delete
	find . -type d -name ".venv" -not -path "./.git/*" -exec rm -rf {} +

# ── Code Quality ───────────────────────────────────────────────────────────────

format:
	cd pipeline && uv run isort . --skip Dolphin --skip html-to-markdown --skip .venv && \
		uv run black . --exclude "(Dolphin|html-to-markdown|\.venv)"
	cd backend  && uv run isort . --skip .venv && uv run black . --exclude "\.venv"

lint:
	cd pipeline && uv run ruff check . --exclude Dolphin,html-to-markdown,.venv && \
		uv run pylint . --ignore=Dolphin,html-to-markdown,.venv
	cd backend  && uv run ruff check . --exclude .venv && uv run pylint . --ignore=.venv

typecheck:
	cd pipeline && uv run mypy . --ignore-missing-imports --explicit-package-bases \
		--exclude "Dolphin|html-to-markdown"
	cd backend  && uv run mypy . --ignore-missing-imports --explicit-package-bases

check: lint typecheck

# Auto-format, apply safe lint fixes, then report remaining issues
code-quality: format
	cd pipeline && uv run ruff check --fix . --exclude Dolphin,html-to-markdown,.venv && \
		uv run pylint . --ignore=Dolphin,html-to-markdown,.venv && \
		uv run mypy . --ignore-missing-imports --explicit-package-bases --exclude "Dolphin|html-to-markdown|\.venv"
	cd backend  && uv run ruff check --fix . --exclude .venv && \
		uv run pylint . --ignore=.venv && \
		uv run mypy . --ignore-missing-imports --explicit-package-bases --exclude "\.venv"

# ── Local infrastructure (Docker Compose) ─────────────────────────────────────
# Starts only Postgres, Redis, and MinIO — app processes run natively.

infra-up:
	docker compose up -d postgres redis minio

infra-down:
	docker compose stop postgres redis minio

# Wipe all local storage (Postgres, Redis, MinIO volumes) and re-apply migrations.
# Use this to get back to a clean slate during development.
dev-reset:
	docker compose down -v postgres redis minio
	docker compose up -d postgres redis minio
	@echo "Waiting for Postgres to be ready…"
	@until docker compose exec postgres pg_isready -U pdf -d pdf_parser -q 2>/dev/null; do sleep 1; done
	cd backend && PYTHONPATH=.. uv run alembic upgrade head

# Run Alembic migrations (apply all pending upgrades)
db-migrate:
	cd backend && PYTHONPATH=.. uv run alembic upgrade head

# ── Local dev servers ─────────────────────────────────────────────────────────

dev-api:
	cd backend && PYTHONPATH=.. uv run uvicorn backend.main:app --reload --port 8000

dev-worker:
	cd backend && PYTHONPATH=.. uv run python -m arq backend.worker.tasks.WorkerSettings

dev-frontend:
	cd frontend && npm run dev

## Run pipeline CLI. Pass DATA_DIR to set input directory:
##   make dev-pipeline DATA_DIR=/path/to/pdfs
dev-pipeline:
	cd pipeline && uv run python main.py $(if $(DATA_DIR),--data-dir $(DATA_DIR),)

## Start API + worker + frontend in parallel (requires infra-up first).
## Each process logs to its own file under logs/; tail -f logs/*.log to follow.
dev:
	@mkdir -p logs
	@echo "Starting API, worker, and frontend in parallel…"
	@echo "  API    → http://localhost:8000"
	@echo "  Frontend → http://localhost:3000"
	@echo "Press Ctrl-C to stop all."
	@trap 'kill 0' INT; \
	  (cd backend  && PYTHONPATH=.. uv run uvicorn backend.main:app --reload --port 8000 2>&1 | tee ../logs/api.log) & \
	  (cd backend  && PYTHONPATH=.. uv run python -m arq backend.worker.tasks.WorkerSettings 2>&1 | tee ../logs/worker.log) & \
	  (cd frontend && npm run dev 2>&1 | tee ../logs/frontend.log) & \
	  wait

# ── Docker ────────────────────────────────────────────────────────────────────

docker-up:
	docker compose up --build

docker-down:
	docker compose down

# ── Local HTTPS (mkcert) ──────────────────────────────────────────────────────

## Generate locally-trusted TLS certificates for localhost using mkcert.
## Run once after cloning (or after `mkcert -install`).
##
## macOS:   brew install mkcert && brew install nss  # nss needed for Firefox
## Linux:   sudo apt install mkcert
## Windows: choco install mkcert
certs:
	@command -v mkcert >/dev/null 2>&1 || { \
	  echo "mkcert not found. Install it first:"; \
	  echo "  macOS:   brew install mkcert && brew install nss"; \
	  echo "  Linux:   sudo apt install mkcert"; \
	  echo "  Windows: choco install mkcert"; \
	  exit 1; }
	mkcert -install
	mkdir -p traefik/certs
	mkcert \
	  -cert-file traefik/certs/localhost.pem \
	  -key-file  traefik/certs/localhost-key.pem \
	  localhost 127.0.0.1 ::1
	@echo ""
	@echo "Certificates written to traefik/certs/"
	@echo "Run 'make docker-up-tls' to start with HTTPS."

## Start all services with local HTTPS (requires 'make certs' first).
docker-up-tls:
	docker compose -f docker-compose.yml -f docker-compose.dev-tls.yml up --build
