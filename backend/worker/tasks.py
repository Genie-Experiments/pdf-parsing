"""
ARQ worker tasks.

Start worker (from backend/ directory):
    python -m arq worker.tasks.WorkerSettings
"""

import asyncio
import tempfile
import uuid
from pathlib import Path

from arq.connections import RedisSettings
from sqlalchemy import update

from core import storage
from core.config import settings
from core.database import AsyncSessionLocal
from models.job import Job, JobStatus
from worker.pipeline import run_pipeline_for_job


async def startup(ctx: dict) -> None:
    """
    Reset any jobs stuck in 'running' back to 'queued'.

    This handles the case where a worker process was killed mid-task, leaving
    jobs in the running state with no worker to complete them.
    """
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Job)
            .where(Job.status == JobStatus.running)
            .values(status=JobStatus.queued)
        )
        await session.commit()


async def run_pipeline(ctx: dict, job_id: str) -> None:
    """
    ARQ task: download PDF from MinIO, run pipeline, upload results.
    Publishes sentinel __DONE__ or __ERROR__ to Redis when finished.
    """
    log_channel = f"job:{job_id}:logs"
    job_uuid = uuid.UUID(job_id)  # parse once; avoids str/UUID PK mismatch
    # Use the ARQ-managed Redis pool from context — no need to open a new connection.
    redis = ctx["redis"]
    pdf_key: str | None = None

    try:
        # ── mark running; capture all job fields in one session ───────────────
        async with AsyncSessionLocal() as session:
            job: Job = await session.get(Job, job_uuid)
            if not job:
                return
            if job.status == JobStatus.cancelled:
                return  # cancelled before the worker picked it up
            pdf_key = job.pdf_key
            page = job.page
            segments_to_refine = job.segments_to_refine
            process_code_using_llm = job.process_code_using_llm
            process_figures_using_llm = job.process_figures_using_llm
            job.status = JobStatus.running
            await session.commit()

        # ── download + run pipeline (sync, in thread) ─────────────────────────
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
                tmp_path = Path(tmp_pdf.name)

            await asyncio.to_thread(storage.download_file, pdf_key, tmp_path)

            result = await asyncio.to_thread(
                run_pipeline_for_job,
                job_id=job_id,
                pdf_path=tmp_path,
                log_channel=log_channel,
                page=page,
                segments_to_refine=segments_to_refine,
                process_code_using_llm=process_code_using_llm,
                process_figures_using_llm=process_figures_using_llm,
            )
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

        # ── upload outputs ────────────────────────────────────────────────────
        md_key = f"jobs/{job_id}/output/result.md"
        seg_key = f"jobs/{job_id}/output/segments.json"
        await asyncio.to_thread(
            storage.upload_bytes, md_key, result["markdown_bytes"], "text/markdown"
        )
        await asyncio.to_thread(
            storage.upload_bytes,
            seg_key,
            result["dolphin_json_bytes"],
            "application/json",
        )
        for fig_name, fig_bytes in result.get("figure_files", {}).items():
            fig_key = f"jobs/{job_id}/output/figures/{fig_name}"
            await asyncio.to_thread(storage.upload_bytes, fig_key, fig_bytes, "image/png")

        # ── mark done ────────────────────────────────────────────────────────
        async with AsyncSessionLocal() as session:
            job = await session.get(Job, job_uuid)
            job.status = JobStatus.done
            job.markdown_key = md_key
            job.segments_key = seg_key
            await session.commit()

        await redis.publish(log_channel, "__DONE__")

    except Exception as exc:
        await redis.publish(log_channel, f"[ERROR] {exc}")
        await redis.publish(log_channel, "__ERROR__")

        async with AsyncSessionLocal() as session:
            job = await session.get(Job, job_uuid)
            if job:
                job.status = JobStatus.failed
                job.error_message = str(exc)
                await session.commit()


class WorkerSettings:
    functions = [run_pipeline]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = settings.worker_max_jobs
    job_timeout = settings.worker_job_timeout
