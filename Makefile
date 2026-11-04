SHELL := /bin/bash

.PHONY: submodules model \
        install-pipeline install-pipeline-gpu install install-dev \
        setup-pipeline setup-pipeline-gpu setup \
        clean \
        format lint typecheck check code-quality \
        infra-up infra-down db-migrate dev-reset \
        dev-api dev-worker dev-frontend dev-pipeline dev \
        docker-up docker-down \
        set-quota \
        check-uv \
        bench-install bench-setup bench-setup-cpu bench-setup-gpu \
        bench-device bench-download bench-download-test \
        bench-data bench-data-test bench-preflight \
        bench-calibrate bench-test bench-run bench-rescore bench-prewarm \
        bench-leaderboard bench-report \
        bench-run-bg bench-status bench-watch bench-stop bench-retry-failed

# ── Setup ──────────────────────────────────────────────────────────────────────

submodules:
	git submodule update --init --recursive

# Everything here runs through uv. One clear message beats a confusing failure
# several targets deep on a machine that has never had it.
check-uv:
	@command -v uv >/dev/null 2>&1 || { \
	  echo "uv is not installed, and every target here needs it. Install it with:"; \
	  echo "    curl -LsSf https://astral.sh/uv/install.sh | sh"; \
	  echo "    brew install uv"; \
	  exit 1; \
	}

# Called through the library rather than a console script: huggingface-hub
# renamed `huggingface-cli` to `hf` in 1.0 and the old name now exits 1, so
# either console script breaks on some pinned version. The function does not.
model:
	@if [ -d pipeline/hf_model ] && [ "$$(ls -A pipeline/hf_model 2>/dev/null)" ]; then \
	  echo "Model weights already present at pipeline/hf_model/ — skipping download."; \
	else \
	  echo "Downloading the ~770 MB Dolphin weights into pipeline/hf_model/ ..."; \
	  cd pipeline && uv run python -c "from huggingface_hub import snapshot_download; \
	    snapshot_download('ByteDance/Dolphin-1.5', local_dir='./hf_model')"; \
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
	cd backend  && uv sync --extra ml
	cd frontend && npm install

install-dev:
	cd pipeline && uv sync --extra ml --group dev
	cd backend  && uv sync --extra ml --group dev
	cd benchmark && uv sync --group dev
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
	rm -rf frontend/.next frontend/node_modules frontend/tsconfig.tsbuildinfo

# ── Code Quality ───────────────────────────────────────────────────────────────

format:
	cd pipeline && uv run isort . --skip Dolphin --skip html-to-markdown --skip .venv && \
		uv run black . --exclude "(Dolphin|html-to-markdown|\.venv)"
	cd backend  && uv run isort . --skip .venv && uv run black . --exclude "\.venv"
	cd benchmark && uv run isort . --skip .venv && uv run black . --exclude "\.venv"

lint:
	cd pipeline && uv run ruff check . --exclude Dolphin,html-to-markdown,.venv && \
		uv run pylint . --ignore=Dolphin,html-to-markdown,.venv
	cd backend  && uv run ruff check . --exclude .venv && uv run pylint . --ignore=.venv
	cd benchmark && uv run ruff check . --exclude .venv && uv run pylint . --ignore=.venv

typecheck:
	cd pipeline && uv run mypy . --ignore-missing-imports --explicit-package-bases \
		--exclude "Dolphin|html-to-markdown"
	cd backend  && uv run mypy . --ignore-missing-imports --explicit-package-bases
	cd benchmark && uv run mypy . --ignore-missing-imports --explicit-package-bases

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
	set -a && source .env && set +a && cd backend && PYTHONPATH=.. uv run alembic upgrade head

# Run Alembic migrations (apply all pending upgrades)
db-migrate:
	set -a && source .env && set +a && cd backend && PYTHONPATH=.. uv run alembic upgrade head

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

# ── Admin ──────────────────────────────────────────────────────────────────────

## Set page quota for a user. EMAIL and QUOTA are required.
##   make set-quota EMAIL=user@example.com QUOTA=500
set-quota:
	@if [ -z "$(EMAIL)" ] || [ -z "$(QUOTA)" ]; then \
	  echo "Usage: make set-quota EMAIL=user@example.com QUOTA=500"; exit 1; \
	fi
	docker compose exec postgres psql -U pdf -d pdf_parser \
	  -c "INSERT INTO user_quota (email, page_quota, pages_used) VALUES ('$(EMAIL)', $(QUOTA), 0) \
	      ON CONFLICT (email) DO UPDATE SET page_quota = $(QUOTA);"
	@echo "Quota for $(EMAIL) set to $(QUOTA) pages."

# ── ParseBench ────────────────────────────────────────────────────────────────
# Scores the pipeline against LlamaIndex's ParseBench. Dolphin inference is the
# whole cost, so calibrate on the target machine before committing to a full run.

## Pipeline variant to score: genieparse (no LLM) or genieparse_llm (GPT-4o on
## figures and code — needs OPENAI_API_KEY and bills per figure).
BENCH_PIPELINE ?= genieparse
## Parallel pages. Each one is a Dolphin subprocess holding its own copy of the
## model, so raise this only as far as RAM and cores allow.
BENCH_CONCURRENCY ?= 1
BENCH_OUTPUT ?= output
## Score a single dimension: chart, table, layout, text_content, text_formatting.
GROUP ?=
BENCH_RUN := cd benchmark && uv run genieparse-bench

bench-install:
	cd benchmark && uv sync

# Pipeline venv + model weights + benchmark deps — everything a fresh machine needs.
## Set up the benchmark on a CPU-only machine. This is the default: use it on
## any Mac, and on a Linux box without an NVIDIA card.
bench-setup bench-setup-cpu: check-uv submodules install-pipeline model bench-install
	@echo
	@echo "Setup done (CPU build of torch)."
	@echo "Check what Dolphin will use here:  make bench-device"
	@echo "Then time this machine:            make bench-calibrate"

## Set up the benchmark on an NVIDIA GPU machine — the same thing, but with a
## CUDA build of torch. Everything after setup is identical: Dolphin picks CUDA
## on its own, so bench-calibrate / bench-prewarm / bench-run do not change.
## Check your driver's CUDA version first (nvidia-smi) and override if needed:
##   make bench-setup-gpu CUDA_VERSION=cu121
bench-setup-gpu: check-uv submodules install-pipeline-gpu model bench-install
	@echo
	@echo "Setup done (CUDA $(CUDA_VERSION) build of torch)."
	@echo "Confirm Dolphin actually sees the GPU:  make bench-device"
	@echo "Then time this machine:                 make bench-calibrate"

## Report the device Dolphin will use here, by asking the pipeline's own torch.
## Run it after setup — a CPU answer on a GPU box means the CUDA build did not
## take, and the whole run would quietly go at CPU speed.
bench-device:
	@cd benchmark && uv run python -c \
	  "from genieparse_bench.calibrate import torch_device; print(torch_device())"

bench-download:
	$(BENCH_RUN) download

bench-download-test:
	$(BENCH_RUN) download --test

# Without the pipeline venv the provider falls back to a bare system python that
# has no torch, and without the weights Dolphin cannot load — either way every
# page fails the same way, for as long as the run lasts. Say so once, up front.
bench-preflight:
	@test -x pipeline/.venv/bin/python || { \
	  echo "The pipeline virtualenv is missing — run 'make bench-setup' first."; \
	  exit 1; \
	}
	@test -n "$$(ls -A pipeline/hf_model 2>/dev/null)" || { \
	  echo "The Dolphin weights are missing — run 'make bench-setup' first."; \
	  exit 1; \
	}

# The dataset is not in git, so calibrate and run fetch what they need on first
# use and stay one command each on a fresh clone. Both guards only fire on an
# empty directory, so a deliberate single-group download is never re-pulled.
bench-data-test:
	@cd benchmark && if [ -z "$$(find data/test -name '*.pdf' -print -quit 2>/dev/null)" ]; then \
	  echo "No test subset yet — fetching the 12-page smoke set."; \
	  uv run genieparse-bench download --test; \
	fi

bench-data:
	@cd benchmark && if [ -z "$$(find data/docs -name '*.pdf' -print -quit 2>/dev/null)" ]; then \
	  echo "No dataset yet — fetching the full 2,078-page ParseBench set."; \
	  uv run genieparse-bench download; \
	fi

## Time one page on this machine and project a full run.
##   make bench-calibrate RUNS=3
RUNS ?= 1
bench-calibrate: bench-preflight bench-data-test
	cd benchmark && uv run python -m genieparse_bench.calibrate \
	  --runs $(RUNS) --concurrency $(BENCH_CONCURRENCY)

## Smoke test on the small dataset (3 files per category) before a full run.
## Writes to its own directory so it cannot seed the real run with results.
BENCH_TEST_OUTPUT ?= output-test
bench-test: bench-preflight bench-data-test
	$(BENCH_RUN) run $(BENCH_PIPELINE) --test \
	  --output_dir $(BENCH_TEST_OUTPUT) \
	  --max_concurrent $(BENCH_CONCURRENCY) --open_report=False

## Full benchmark. Results land in benchmark/$(BENCH_OUTPUT)/$(BENCH_PIPELINE)/.
##   make bench-run BENCH_CONCURRENCY=4
##   make bench-run GROUP=table
bench-run: bench-preflight bench-data
	$(BENCH_RUN) run $(BENCH_PIPELINE) \
	  --output_dir $(BENCH_OUTPUT) \
	  --max_concurrent $(BENCH_CONCURRENCY) \
	  --open_report=False \
	  $(if $(GROUP),--group $(GROUP),)

## Re-score existing inference output without re-running Dolphin. Post-processing
## is ~0.2s/page, so this is the loop to iterate on.
bench-rescore:
	$(BENCH_RUN) run $(BENCH_PIPELINE) \
	  --output_dir $(BENCH_OUTPUT) --skip_inference --open_report=False \
	  $(if $(GROUP),--group $(GROUP),)

## Pre-compute Dolphin inference, loading the model once per chunk instead of
## once per page. The per-page cold start is ~5s (mostly importing torch and
## transformers); on CPU that hides behind inference, on a GPU it does not.
## Safe to interrupt — cached pages stay, so re-running resumes.
##   make bench-prewarm CHUNK=100
CHUNK ?= 50
bench-prewarm: bench-preflight bench-data
	cd benchmark && uv run python -m genieparse_bench.prewarm --chunk-size $(CHUNK)

bench-leaderboard:
	$(BENCH_RUN) leaderboard

## Serve the HTML reports (PDF rendering needs http://, not file://).
bench-report:
	$(BENCH_RUN) serve $(BENCH_PIPELINE)

# ── ParseBench: long runs ─────────────────────────────────────────────────────
# A full run takes hours. Completed pages are written one JSON file each, so
# re-running resumes where it stopped — bench-run and bench-run-bg are both safe
# to repeat after a crash, a reboot, or a dropped SSH session.

BENCH_LOG ?= logs/bench-$(BENCH_PIPELINE).log
BENCH_PID ?= run.pid

## Start a full run detached, surviving logout and connection loss.
## Follow it with 'make bench-watch', check it with 'make bench-status'.
## `set -m` puts the run in its own process group so bench-stop can take the
## whole tree down; $$! must be read in the same shell that did the cd, or the
## pid file lands in the wrong directory and records the wrong process.
bench-run-bg: bench-preflight bench-data
	@cd benchmark; \
	  mkdir -p $(dir $(BENCH_LOG)); \
	  if [ -f $(BENCH_PID) ] && kill -0 $$(cat $(BENCH_PID)) 2>/dev/null; then \
	    echo "A run is already going (pid $$(cat $(BENCH_PID))). Stop it with 'make bench-stop'."; \
	    exit 1; \
	  fi; \
	  set -m; \
	  nohup uv run genieparse-bench run $(BENCH_PIPELINE) \
	    --output_dir $(BENCH_OUTPUT) \
	    --max_concurrent $(BENCH_CONCURRENCY) \
	    --open_report=False \
	    $(if $(GROUP),--group $(GROUP),) \
	    >> $(BENCH_LOG) 2>&1 & \
	  pid=$$!; \
	  echo $$pid > $(BENCH_PID); \
	  echo "Started pid $$pid, logging to benchmark/$(BENCH_LOG)"

## Pages completed per dimension, and whether a run is alive.
bench-status:
	@cd benchmark && uv run python -m genieparse_bench.status \
	  --pipeline $(BENCH_PIPELINE) --output-dir $(BENCH_OUTPUT) --pid-file $(BENCH_PID)

bench-watch:
	@cd benchmark && touch $(BENCH_LOG) && tail -f $(BENCH_LOG)

## Stop a detached run. Finished pages are kept; restart to resume.
## Signals the process group, so Dolphin subprocesses go too.
bench-stop:
	@cd benchmark; \
	  if [ -f $(BENCH_PID) ] && kill -0 $$(cat $(BENCH_PID)) 2>/dev/null; then \
	    pid=$$(cat $(BENCH_PID)); \
	    kill -TERM -$$pid 2>/dev/null || kill -TERM $$pid 2>/dev/null || true; \
	    echo "Stopped pid $$pid. Re-run to resume where it left off."; \
	    rm -f $(BENCH_PID); \
	  else \
	    echo "No run in progress."; rm -f $(BENCH_PID); \
	  fi

## Re-run only the pages that failed, leaving completed ones alone.
## Failures write no result file, so this is just a normal resume.
bench-retry-failed: bench-run
