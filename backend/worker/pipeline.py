"""
Thin wrapper that runs the existing pipeline steps for a single PDF.
All business logic stays in the original pipeline/ modules — this file
only handles temp dirs, env wiring, and log forwarding to Redis.

Designed to be called via asyncio.to_thread from the ARQ worker task.
"""

import logging
import tempfile
from pathlib import Path

import redis as sync_redis

from core.config import settings

# Dolphin submodule lives inside the pipeline directory
PIPELINE_ROOT = Path(__file__).parent.parent.parent / "pipeline"
DOLPHIN_SCRIPT = str(PIPELINE_ROOT / "Dolphin" / "demo_page.py")

# Model weights live inside the pipeline directory alongside the Dolphin submodule.
MODEL_PATH = str(PIPELINE_ROOT / "hf_model")


class RedisLogHandler(logging.Handler):
    """
    Forwards log records to a Redis pub/sub channel.

    Uses the synchronous Redis client because logging.Handler.emit() is a
    synchronous call, and this handler runs in a worker thread
    (via asyncio.to_thread) — not in the async event loop.
    """

    def __init__(self, channel: str):
        super().__init__()
        self.channel = channel
        self._redis = sync_redis.from_url(settings.redis_url)

    def emit(self, record: logging.LogRecord) -> None:
        self.publish_raw(self.format(record))

    def publish_raw(self, message: str) -> None:
        """Publish an arbitrary string to the log channel (bypasses log formatting)."""
        try:
            self._redis.publish(self.channel, message)
        except Exception:
            pass  # never let logging break the pipeline

    def close(self) -> None:
        try:
            self._redis.close()
        except Exception:
            pass
        super().close()


_DEFAULT_SEGMENTS = ["code", "fig", "tab"]


def run_pipeline_for_job(
    job_id: str,
    pdf_path: Path,
    log_channel: str,
    page: int | None = None,
    segments_to_refine: list[str] | None = None,
    process_code_using_llm: bool = False,
    process_figures_using_llm: bool = False,
) -> dict:
    """
    Execute all 10 pipeline steps for a single PDF.
    Runs synchronously — must be called via asyncio.to_thread from async code.

    Returns:
        {
            "markdown_bytes": bytes,
            "dolphin_json_bytes": bytes,
        }
    """
    from post_processing.fix_bullet_points.fix_bullet_points import (
        fix_bullet_points_batch,
    )
    from post_processing.fix_ocr_errors.fix_ocr_errors import fix_ocr_errors_batch
    from post_processing.fix_ocr_errors.get_text_from_pdf import extract_all_pdf_texts
    from post_processing.markdown_sections_post_processing.fix_markdown_sections import (
        batch_fix_markdown_sections,
    )
    from post_processing.markdown_sections_post_processing.section_hierarchy_from_pdf import (
        batch_process_pdfs,
    )
    from post_processing.process_json_files import process_all_json_files
    from post_processing.remove_headers_and_footers.insert_page_breaks import (
        insert_page_breaks_batch,
    )
    from post_processing.remove_headers_and_footers.remove_headers_footers import (
        remove_headers_footers_batch,
    )
    from process_pdf_files.process_pdf_files import process_pdf_files
    from utils.create_backups_md import create_markdown_backup

    handler = RedisLogHandler(log_channel)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)

    try:
        with tempfile.TemporaryDirectory(prefix=f"pdf_job_{job_id}_") as tmp:
            data_dir = Path(tmp) / "data"
            output_dir = Path(tmp) / "output"
            raw_text_dir = output_dir / "_pipeline" / "raw_text"
            hierarchy_dir = output_dir / "_pipeline" / "section_hierarchy"
            data_dir.mkdir()
            output_dir.mkdir()

            # If a single page was requested, extract it from the PDF first
            if page is not None:
                import fitz  # pymupdf — available as a pipeline base dep

                doc = fitz.open(str(pdf_path))
                total = len(doc)
                if page < 1 or page > total:
                    raise ValueError(
                        f"Page {page} is out of range (PDF has {total} pages)"
                    )
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=page - 1, to_page=page - 1)
                page_pdf_name = f"{pdf_path.stem}_page{page}.pdf"
                page_pdf_path = Path(tmp) / page_pdf_name
                new_doc.save(str(page_pdf_path))
                doc.close()
                new_doc.close()
                handler.publish_raw(
                    f"[INFO] Extracted page {page}/{total} for processing"
                )
                dest = data_dir / page_pdf_name
                dest.write_bytes(page_pdf_path.read_bytes())
                effective_stem = page_pdf_path.stem
            else:
                dest = data_dir / pdf_path.name
                dest.write_bytes(pdf_path.read_bytes())
                effective_stem = pdf_path.stem

            def _step(n: int, label: str, fn):
                handler.publish_raw(f"\n{'='*60}\nSTEP {n}: {label}\n{'='*60}")
                fn()

            _step(
                1,
                "Processing PDF with Dolphin model",
                lambda: process_pdf_files(
                    str(data_dir),
                    str(output_dir),
                    DOLPHIN_SCRIPT,
                    MODEL_PATH,
                    settings.dolphin_max_batch_size,
                ),
            )
            _step(
                2,
                "Extracting raw text",
                lambda: extract_all_pdf_texts(str(data_dir), str(raw_text_dir)),
            )
            _step(
                3,
                "Generating section hierarchy JSONs",
                lambda: batch_process_pdfs(
                    data_directory=str(data_dir),
                    output_base_dir=str(hierarchy_dir),
                    min_heading_size=12,
                    max_levels=6,
                    bold_only=False,
                    exclude_headers_footers=True,
                ),
            )
            _step(
                4,
                "Creating markdown backups",
                lambda: create_markdown_backup(str(output_dir)),
            )
            _step(
                5,
                "Refining segments",
                lambda: process_all_json_files(
                    str(output_dir),
                    (
                        segments_to_refine
                        if segments_to_refine is not None
                        else _DEFAULT_SEGMENTS
                    ),
                    process_code_using_llm,
                    process_figures_using_llm,
                ),
            )
            _step(
                6,
                "Inserting page breaks",
                lambda: insert_page_breaks_batch(str(output_dir)),
            )
            _step(
                7,
                "Removing headers/footers",
                lambda: remove_headers_footers_batch(str(output_dir)),
            )
            _step(
                8,
                "Fixing OCR errors",
                lambda: fix_ocr_errors_batch(str(output_dir), str(raw_text_dir)),
            )
            _step(
                9,
                "Fixing markdown section hierarchy",
                lambda: batch_fix_markdown_sections(
                    str(hierarchy_dir), str(output_dir)
                ),
            )
            _step(
                10,
                "Standardizing bullet points",
                lambda: fix_bullet_points_batch(str(output_dir)),
            )

            # ── deterministic output resolution ───────────────────────────────
            # Pipeline writes outputs under output_dir/<stem>/ per README:
            #   markdown/<stem>.md
            #   recognition_json/<stem>.json
            # For single-page runs the stem is e.g. "doc_page5".
            md_path = output_dir / effective_stem / "markdown" / f"{effective_stem}.md"
            json_path = (
                output_dir
                / effective_stem
                / "recognition_json"
                / f"{effective_stem}.json"
            )

            if not md_path.exists():
                # Fallback: first non-backup .md outside the _pipeline dir
                candidates = [
                    p
                    for p in output_dir.rglob("*.md")
                    if "_backup" not in p.name and "_pipeline" not in str(p)
                ]
                if not candidates:
                    raise FileNotFoundError(
                        f"Pipeline produced no markdown output for '{effective_stem}'"
                    )
                md_path = candidates[0]

            if not json_path.exists():
                candidates = [
                    p for p in output_dir.rglob("*.json") if "_pipeline" not in str(p)
                ]
                if not candidates:
                    raise FileNotFoundError(
                        f"Pipeline produced no JSON output for '{effective_stem}'"
                    )
                json_path = candidates[0]

            return {
                "markdown_bytes": md_path.read_bytes(),
                "dolphin_json_bytes": json_path.read_bytes(),
            }

    finally:
        root.removeHandler(handler)
        handler.close()  # closes the Redis connection
