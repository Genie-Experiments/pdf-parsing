"""
Job lifecycle routes:
  POST   /jobs              Upload PDF → create job → enqueue worker
  GET    /jobs              List jobs for the authenticated user (paginated)
  GET    /jobs/{id}         Get single job status (owner only)
  GET    /jobs/{id}/logs    SSE stream of live pipeline logs (owner only)
  GET    /jobs/{id}/result  Markdown text + presigned PDF URL (owner only)
  DELETE /jobs/{id}         Cancel / delete a job (owner only)
"""

import asyncio
import uuid
from typing import AsyncGenerator, List, Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from sse_starlette.sse import EventSourceResponse

from api.deps import db_session, require_auth
from core import storage
from core.config import settings
from models.job import Job, JobRead, JobStatus
from models.user_quota import UserQuota

router = APIRouter(prefix="/jobs", tags=["jobs"])

_PDF_MAGIC = b"%PDF"


# ── helpers ───────────────────────────────────────────────────────────────────


async def _get_owned_job(
    job_id: uuid.UUID,
    email: str,
    session: AsyncSession,
) -> Job:
    """Fetch a job and verify ownership. Used for mutating operations (delete)."""
    job = await session.get(Job, job_id)
    if not job or job.user_email != email:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


async def _get_job(job_id: uuid.UUID, session: AsyncSession) -> Job:
    """Fetch any job by ID regardless of owner. Returns 404 if not found."""
    job = await session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


# ── routes ────────────────────────────────────────────────────────────────────


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
async def create_job(
    request: Request,
    file: UploadFile,
    page: Optional[int] = Form(
        None, description="Process only this page (1-indexed). Omit for full PDF."
    ),
    segments_to_refine: Optional[str] = Form(
        None,
        description=(
            "Comma-separated segment types to refine. "
            "Valid values: code, fig, tab, catalogue. "
            'Omit for default ["code","fig","tab"].'
        ),
    ),
    process_code_using_llm: bool = Form(
        False, description="Run GPT-4o Vision on code blocks."
    ),
    process_figures_using_llm: bool = Form(
        False, description="Run GPT-4o Vision on figures."
    ),
    session: AsyncSession = Depends(db_session),
    email: str = Depends(require_auth),
) -> Job:
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    # Read up to limit+1 bytes to detect oversized uploads without buffering the whole file
    chunk = await file.read(settings.max_upload_bytes + 1)
    if len(chunk) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.max_upload_bytes / (1024 * 1024):.0f} MB limit.",
        )
    pdf_bytes = chunk

    # Validate PDF magic bytes — rejects non-PDF files regardless of extension
    if not pdf_bytes.startswith(_PDF_MAGIC):
        raise HTTPException(
            status_code=400, detail="File does not appear to be a valid PDF."
        )

    if page is not None and page < 1:
        raise HTTPException(status_code=400, detail="page must be 1 or greater.")

    # Parse comma-separated segments string → list (None = use pipeline default)
    _VALID_SEGMENTS = {"code", "fig", "tab", "catalogue"}
    parsed_segments: Optional[List[str]] = None
    if segments_to_refine is not None:
        parsed_segments = [
            s.strip() for s in segments_to_refine.split(",") if s.strip()
        ]
        invalid = set(parsed_segments) - _VALID_SEGMENTS
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid segment type(s): {', '.join(sorted(invalid))}. "
                f"Valid values: {', '.join(sorted(_VALID_SEGMENTS))}.",
            )

    # Open the PDF once here — used for page-count validation and quota calculation.
    # The bytes are already in memory from the upload read above.
    import fitz  # pymupdf — available via pdf-pipeline path dep

    pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(pdf_doc)
    pdf_doc.close()

    if page is None and total_pages > settings.max_pdf_pages:
        raise HTTPException(
            status_code=400,
            detail=f"PDF has {total_pages} pages — full-document processing is limited to {settings.max_pdf_pages} pages. Use single-page mode instead.",
        )

    if page is not None and page > total_pages:
        raise HTTPException(
            status_code=400,
            detail=f"page {page} is out of range — PDF has {total_pages} page(s).",
        )

    # ── quota check ───────────────────────────────────────────────────────────
    # Pages are charged at submission time, not on success. A failed job does NOT
    # refund quota. This is intentional: it prevents quota abuse via repeated
    # large-PDF submissions that are cancelled or fail partway through.
    # Skipped in dev mode (BYPASS_QUOTA=true).
    if not settings.bypass_quota:
        # Single-page job costs 1; full-PDF job costs however many pages the PDF has.
        if page is not None:
            pages_to_consume = 1
        else:
            pages_to_consume = total_pages

        quota = await session.get(UserQuota, email)
        if quota is None:
            quota = UserQuota(
                email=email,
                page_quota=settings.default_page_quota,
                pages_used=0,
            )
            session.add(quota)
            await session.flush()  # assign PK before the update below

        remaining = quota.page_quota - quota.pages_used
        if pages_to_consume > remaining:
            raise HTTPException(
                status_code=402,
                detail=(
                    f"Page quota exceeded. "
                    f"{quota.pages_used}/{quota.page_quota} pages used; "
                    f"this job requires {pages_to_consume} page(s) but only {remaining} remain."
                ),
            )

        quota.pages_used += pages_to_consume

    # Generate the job ID up front so we can build the storage key before committing.
    # Upload order: MinIO first → DB commit → enqueue.
    # If the upload fails, nothing is persisted. If enqueue fails after commit, the
    # job row exists but no worker picks it up — the startup recovery hook will requeue it.
    job_id = uuid.uuid4()
    pdf_key = f"jobs/{job_id}/input/{file.filename}"
    await asyncio.to_thread(storage.upload_bytes, pdf_key, pdf_bytes, "application/pdf")

    job = Job(
        id=job_id,
        filename=file.filename,
        user_email=email,
        page=page,
        segments_to_refine=parsed_segments,
        process_code_using_llm=process_code_using_llm,
        process_figures_using_llm=process_figures_using_llm,
        pdf_key=pdf_key,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    # Enqueue worker task
    await request.app.state.arq.enqueue_job("run_pipeline", str(job.id))

    return job


@router.get("", response_model=List[JobRead])
async def list_jobs(
    session: AsyncSession = Depends(db_session),
    email: str = Depends(require_auth),
    scope: str = "all",
    limit: int = 50,
    offset: int = 0,
) -> List[Job]:
    """Return jobs newest first. scope=all returns all users; scope=mine filters to the caller."""
    limit = min(limit, 100)
    stmt = select(Job).order_by(Job.created_at.desc()).limit(limit).offset(offset)
    if scope == "mine":
        stmt = stmt.where(Job.user_email == email)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/stats", summary="Job counts by status")
async def job_stats(
    session: AsyncSession = Depends(db_session),
    email: str = Depends(require_auth),
    scope: str = "all",
) -> dict:
    """Returns job counts grouped by status. scope=all aggregates all users; scope=mine filters to the caller."""
    stmt = select(Job.status, sa_func.count(Job.id)).group_by(Job.status)
    if scope == "mine":
        stmt = stmt.where(Job.user_email == email)
    rows = await session.execute(stmt)
    counts: dict[str, int] = {s: 0 for s in ("queued", "running", "done", "failed")}
    for job_status, count in rows.all():
        counts[job_status] = count
    return counts


@router.get("/{job_id}", response_model=JobRead)
async def get_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(db_session),
    email: str = Depends(require_auth),
) -> JobRead:
    job = await _get_job(job_id, session)
    redis = aioredis.from_url(settings.redis_url)
    try:
        step_val = await redis.get(f"job:{job_id}:step")
        current_step = int(step_val) if step_val else 0
    finally:
        await redis.aclose()
    return JobRead(**job.model_dump(), current_step=current_step)


@router.get("/{job_id}/logs")
async def stream_logs(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(db_session),
    _: str = Depends(require_auth),
) -> EventSourceResponse:
    """
    SSE endpoint. The worker publishes log lines to Redis channel
    `job:{job_id}:logs`. We subscribe and forward to the client.
    - Sends automatic pings every 15 s to keep proxies from closing the connection.
    - Times out after `sse_timeout_seconds` if no sentinel is received (e.g. worker crash).
    """
    await _get_job(job_id, session)

    async def _generate() -> AsyncGenerator[dict, None]:
        redis = aioredis.from_url(settings.redis_url)
        pubsub = redis.pubsub()
        channel = f"job:{job_id}:logs"
        await pubsub.subscribe(channel)

        try:
            async with asyncio.timeout(settings.sse_timeout_seconds):
                async for message in pubsub.listen():
                    if message["type"] != "message":
                        continue
                    line: str = message["data"].decode()
                    yield {"data": line}
                    if line in ("__DONE__", "__ERROR__"):
                        break
        except TimeoutError:
            yield {"data": "__TIMEOUT__"}
        finally:
            await pubsub.unsubscribe(channel)
            await redis.aclose()

    return EventSourceResponse(_generate(), ping=15)


@router.get("/{job_id}/result")
async def get_result(
    request: Request,
    job_id: uuid.UUID,
    session: AsyncSession = Depends(db_session),
    _: str = Depends(require_auth),
) -> dict:
    import re

    job = await _get_job(job_id, session)
    if job.status != JobStatus.done:
        raise HTTPException(status_code=409, detail=f"Job is {job.status}, not done.")

    markdown = (
        await asyncio.to_thread(storage.download_bytes, job.markdown_key)
    ).decode("utf-8")

    # Rewrite relative figure references to the backend proxy endpoint so images
    # render without exposing MinIO directly to browsers.
    base = str(request.base_url).rstrip("/")

    def _replace_figure(m: re.Match) -> str:
        alt, filename = m.group(1), m.group(2)
        url = f"{base}/api/v1/jobs/{job_id}/figures/{filename}"
        return f"![{alt}]({url})"

    markdown = re.sub(r"!\[([^\]]*)\]\(figures/([^)]+)\)", _replace_figure, markdown)

    pdf_url = await asyncio.to_thread(storage.presigned_url, job.pdf_key)
    return {"markdown": markdown, "pdf_url": pdf_url}


@router.get("/{job_id}/pdf")
async def get_pdf_url(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(db_session),
    _: str = Depends(require_auth),
) -> dict:
    """Return a presigned URL for the original uploaded PDF (any job status)."""
    job = await _get_job(job_id, session)
    pdf_url = await asyncio.to_thread(storage.presigned_url, job.pdf_key)
    return {"pdf_url": pdf_url}


@router.get("/{job_id}/pdf/content")
async def stream_pdf(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(db_session),
    _: str = Depends(require_auth),
):
    """Stream the original PDF bytes through the API (avoids MinIO CORS issues)."""
    from fastapi.responses import Response

    job = await _get_job(job_id, session)
    pdf_bytes = await asyncio.to_thread(storage.download_bytes, job.pdf_key)
    from urllib.parse import quote
    encoded_filename = quote(job.filename, safe="")
    disposition = f"inline; filename*=UTF-8''{encoded_filename}"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": disposition},
    )


@router.get("/{job_id}/figures/{filename:path}")
async def stream_figure(
    job_id: uuid.UUID,
    filename: str,
    session: AsyncSession = Depends(db_session),
    _: str = Depends(require_auth),
):
    """Stream a figure image through the API (keeps MinIO internal)."""
    import mimetypes
    from fastapi.responses import Response

    await _get_job(job_id, session)
    fig_key = f"jobs/{job_id}/output/figures/{filename}"
    fig_bytes = await asyncio.to_thread(storage.download_bytes, fig_key)
    content_type = mimetypes.guess_type(filename)[0] or "image/png"
    return Response(content=fig_bytes, media_type=content_type)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(db_session),
    email: str = Depends(require_auth),
) -> None:
    """Delete a job record. Only allowed when the job is not actively running."""
    job = await _get_owned_job(job_id, email, session)
    if job.status in (JobStatus.queued, JobStatus.running):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a running job.",
        )
    await session.delete(job)
    await session.commit()
