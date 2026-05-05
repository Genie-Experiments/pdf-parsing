# syntax=docker/dockerfile:1
# ─── Stage 1: dependency builder ─────────────────────────────────────────────
# Pin to a specific uv release tag (replace "latest" with e.g. "0.7.3") for
# reproducible production builds.
FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --extra ml

# ─── Stage 2: runtime image ───────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS runtime

# tini: correct PID 1 signal handling + zombie reaping for Dolphin subprocess
# Cache mounts keep apt lists on the BuildKit host — faster layer rebuilds.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libgomp1 tini \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --no-log-init --create-home --shell /bin/bash appuser

WORKDIR /app

COPY --from=builder --link --chown=appuser:appuser /app/.venv ./.venv

ENV PATH="/app/.venv/bin:$PATH" \
    # Flush stdout/stderr immediately — critical for log visibility in production
    PYTHONUNBUFFERED=1 \
    # Bytecode already compiled at build time by UV_COMPILE_BYTECODE; skip at runtime
    PYTHONDONTWRITEBYTECODE=1 \
    # Must be supplied via -e or docker-compose environment
    DATA_DIRECTORY="" \
    OUTPUT_DIRECTORY=""

COPY --link --chown=appuser:appuser . .

USER appuser

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "main.py"]
