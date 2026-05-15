# syntax=docker/dockerfile:1
# ─── API image: FastAPI + ARQ client only — no ML packages ────────────────────
# This image runs uvicorn (the HTTP API). For the ARQ worker (needs torch etc.)
# use backend/Dockerfile.worker instead.
#
# ─── Stage 1: dependency builder ─────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Copy uv binary directly — no pip, no network, instant layer cache hit.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# UV_LINK_MODE=copy: Docker Desktop uses overlayfs; hardlinks across
#   cache-mount/workdir boundaries silently fail without this.
# UV_COMPILE_BYTECODE=1: pre-compile .pyc at build time → faster container start.
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

# Copy only manifests first — keeps the `uv sync` layer cached as long as
# lockfiles are unchanged (source code edits don't bust this layer).
COPY pipeline/pyproject.toml pipeline/uv.lock ./pipeline/
COPY backend/pyproject.toml backend/uv.lock ./backend/

# Install deps. BuildKit persists /root/.cache/uv on the host across builds —
# only changed/new packages are downloaded on subsequent builds.
RUN --mount=type=cache,target=/root/.cache/uv \
    cd backend && uv sync --frozen --no-dev --no-install-project

# ─── Stage 2: runtime image ───────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# tini: correct PID 1 signal handling + zombie reaping
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libgomp1 tini \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# --link: these COPY layers are cache-independent from the builder stage,
# so a runtime base image update doesn't bust the venv layer.
COPY --from=builder --chown=appuser:appuser /app/backend/.venv ./backend/.venv
ENV PATH="/app/backend/.venv/bin:$PATH" \
    PYTHONPATH="/app/backend"

COPY --chown=appuser:appuser pipeline/ ./pipeline/
COPY --chown=appuser:appuser backend/ ./backend/

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
