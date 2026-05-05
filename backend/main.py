from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import auth, jobs
from core.config import settings
from core.storage import ensure_bucket


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # NOTE: schema is managed exclusively by Alembic migrations.
    # Run `alembic upgrade head` before starting the server.
    ensure_bucket()
    app.state.arq = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    yield
    # Shutdown
    await app.state.arq.aclose()


app = FastAPI(
    title="PDF Parser API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
