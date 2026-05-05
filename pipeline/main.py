import argparse
import os
import shutil
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path

import fitz  # pymupdf

_PIPELINE_ROOT = Path(__file__).parent

from config.config import settings
from post_processing.fix_bullet_points.fix_bullet_points import fix_bullet_points_batch
from post_processing.fix_ocr_errors.fix_ocr_errors import fix_ocr_errors_batch
from post_processing.fix_ocr_errors.get_text_from_pdf import extract_all_pdf_texts
from post_processing.markdown_sections_post_processing.fix_markdown_sections import (
    batch_fix_markdown_sections,
    fix_markdown_headings,
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
from utils.logger import get_logger, log_step, setup_logging

# Internal paths (not user-configurable) — absolute so pipeline works from any CWD
DOLPHIN_SCRIPT = str(_PIPELINE_ROOT / "Dolphin" / "demo_page.py")
MODEL_PATH = str(_PIPELINE_ROOT / "hf_model")

# User-configurable settings
OUTPUT_DIRECTORY = settings.output_directory
PROCESS_CODE_USING_LLM = settings.process_code_using_llm
PROCESS_FIGURES_USING_LLM = settings.process_figures_using_llm
SEGMENTS_TO_REFINE = settings.segments_to_refine
RESUME = settings.resume
START_FROM_STEP = settings.start_from_step
DOLPHIN_MAX_BATCH_SIZE = settings.dolphin_max_batch_size

logger = get_logger(__name__)


def _resolve_data_directory(cli_arg: str | None) -> str:
    """Resolve DATA_DIRECTORY: CLI arg > env/.env > error."""
    if cli_arg:
        return cli_arg
    if settings.data_directory:
        return settings.data_directory
    logger.error(
        "DATA_DIRECTORY is not set. "
        "Provide it via --data-dir, set DATA_DIRECTORY in pipeline/.env, "
        "or export it as an environment variable."
    )
    sys.exit(1)


def _prepare_input(
    cli_data_dir: str | None,
    cli_pdf_file: str | None,
    cli_page: int | None,
) -> tuple[str, str | None]:
    """Resolve the effective DATA_DIRECTORY and an optional temp dir to clean up.

    Returns (data_dir, tmp_dir_to_cleanup).
    tmp_dir_to_cleanup is None when no temp dir was created.
    """
    if cli_pdf_file:
        pdf_path = Path(cli_pdf_file).resolve()
        if not pdf_path.exists():
            logger.error(f"PDF not found: {pdf_path}")
            sys.exit(1)

        if cli_page is not None:
            doc = fitz.open(str(pdf_path))
            total = len(doc)
            if cli_page < 1 or cli_page > total:
                logger.error(
                    f"--page {cli_page} is out of range (PDF has {total} pages)"
                )
                sys.exit(1)
            out_name = f"{pdf_path.stem}_page#{cli_page}.pdf"
            out_path = pdf_path.parent / out_name
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=cli_page - 1, to_page=cli_page - 1)
            new_doc.save(str(out_path))
            doc.close()
            new_doc.close()
            logger.info(f"Extracted page {cli_page}/{total} → {out_path}")
            # Copy into a dedicated temp dir so sibling PDFs aren't processed.
            # The extracted PDF itself remains next to the original permanently.
            tmp = tempfile.mkdtemp(prefix="pdf_pipeline_page_")
            shutil.copy2(str(out_path), tmp)
            return tmp, tmp

        # Single file, no page — copy into temp dir so siblings aren't processed
        tmp = tempfile.mkdtemp(prefix="pdf_pipeline_single_")
        shutil.copy2(str(pdf_path), tmp)
        return tmp, tmp

    return _resolve_data_directory(cli_data_dir), None


def should_run_step(step_num: int, output_check=None) -> bool:
    """Returns True if the step should run, False if it should be skipped.

    - START_FROM_STEP: skips all steps before the given number
    - RESUME: additionally skips steps whose outputs already exist (steps 1-3 only)
    """
    if step_num < START_FROM_STEP:
        logger.info(f"Skipping step {step_num} (START_FROM_STEP={START_FROM_STEP})")
        return False
    if RESUME and output_check is not None and output_check():
        logger.info(f"Skipping step {step_num} (RESUME=true, output already exists)")
        return False
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PDF Parsing Pipeline")
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--data-dir",
        metavar="PATH",
        help="Directory containing input PDFs (overrides DATA_DIRECTORY in .env)",
    )
    input_group.add_argument(
        "--pdf-file",
        metavar="PATH",
        help="Process a single PDF file (overrides --data-dir and DATA_DIRECTORY in .env)",
    )
    parser.add_argument(
        "--page",
        type=int,
        metavar="N",
        help="Extract and process only page N of --pdf-file (1-indexed). Requires --pdf-file.",
    )
    args = parser.parse_args()

    if args.page is not None and args.pdf_file is None:
        parser.error("--page requires --pdf-file")

    DATA_DIRECTORY, _tmp_dir = _prepare_input(args.data_dir, args.pdf_file, args.page)

    # Derived pipeline dirs (consolidated under OUTPUT_DIRECTORY)
    RAW_PDF_TEXT_DIR = os.path.join(OUTPUT_DIRECTORY, "_pipeline", "raw_text")
    HIERARCHY_JSON_DIRECTORY = os.path.join(
        OUTPUT_DIRECTORY, "_pipeline", "section_hierarchy"
    )

    setup_logging(level="INFO", log_file="logs/pdf_parsing.log")

    # Validate model weights exist before step 1 runs (fail fast with a clear message)
    if START_FROM_STEP <= 1:
        model_path_obj = Path(MODEL_PATH)
        if not model_path_obj.exists() or not any(model_path_obj.iterdir()):
            logger.error(
                f"Dolphin model weights not found at '{MODEL_PATH}'.\n"
                "  Download them by running from the repo root:\n"
                "    make setup\n"
                "  or manually:\n"
                "    cd pipeline && uv run huggingface-cli download ByteDance/Dolphin-1.5 --local-dir ./hf_model\n"
                "  To skip step 1 (Dolphin inference) and run steps 2–10 only:\n"
                "    START_FROM_STEP=2 uv run python main.py --data-dir <path>"
            )
            sys.exit(1)

    pipeline_start_time = time.time()
    logger.info("Starting PDF Parsing Pipeline")
    if args.pdf_file:
        logger.info(f"  Input PDF       : {Path(args.pdf_file).resolve()}")
        if args.page:
            logger.info(f"  Single page     : {args.page}")
    else:
        logger.info(f"  Input directory : {DATA_DIRECTORY}")
    logger.info(f"  Output directory: {OUTPUT_DIRECTORY}")
    logger.info(f"  RESUME={RESUME}, START_FROM_STEP={START_FROM_STEP}")
    logger.info("=" * 80)

    # 1. Process PDF Files
    if should_run_step(
        1,
        lambda: (
            any(
                p
                for p in Path(OUTPUT_DIRECTORY).iterdir()
                if p.is_dir() and p.name != "_pipeline"
            )
            if Path(OUTPUT_DIRECTORY).exists()
            else False
        ),
    ):
        log_step(
            1,
            "Processing PDF files for extracting base line markdown with Dolphin model",
        )
        _t = time.time()
        process_pdf_files(
            DATA_DIRECTORY,
            OUTPUT_DIRECTORY,
            DOLPHIN_SCRIPT,
            MODEL_PATH,
            DOLPHIN_MAX_BATCH_SIZE,
        )
        logger.info("Step 1 completed in %.1fs", time.time() - _t)

    logger.info("Starting Post-Processing Steps...")

    # 2. Extract raw text from all PDF files
    if should_run_step(
        2,
        lambda: (
            bool(list(Path(RAW_PDF_TEXT_DIR).rglob("*.txt")))
            if Path(RAW_PDF_TEXT_DIR).exists()
            else False
        ),
    ):
        log_step(
            2,
            f"Extracting raw text from all PDF files and storing them in {RAW_PDF_TEXT_DIR}",
        )
        _t = time.time()
        extract_all_pdf_texts(DATA_DIRECTORY, RAW_PDF_TEXT_DIR)
        logger.info("Step 2 completed in %.1fs", time.time() - _t)

    # 3. Generate section hierarchy JSONs from PDFs
    if should_run_step(
        3,
        lambda: (
            bool(list(Path(HIERARCHY_JSON_DIRECTORY).rglob("*.json")))
            if Path(HIERARCHY_JSON_DIRECTORY).exists()
            else False
        ),
    ):
        log_step(3, "Generating section hierarchy JSONs from PDFs")
        _t = time.time()
        batch_process_pdfs(
            data_directory=DATA_DIRECTORY,
            output_base_dir=HIERARCHY_JSON_DIRECTORY,
            min_heading_size=12,
            max_levels=6,
            bold_only=False,
            exclude_headers_footers=True,
        )
        logger.info("Step 3 completed in %.1fs", time.time() - _t)

    # 4. Create backup of markdown files before post-processing
    if should_run_step(4):
        log_step(4, "Creating backup of markdown files before post-processing")
        _t = time.time()
        backup_count = create_markdown_backup(OUTPUT_DIRECTORY)
        if backup_count:
            logger.info(
                "Successfully created %d backup files with '_backup' suffix",
                backup_count,
            )
        else:
            logger.info(
                "No markdown files found to backup, continuing with post-processing..."
            )
        logger.info("Step 4 completed in %.1fs", time.time() - _t)

    # 5. Process all JSON files in results directory
    if should_run_step(5):
        log_step(5, "Processing JSON files for segment refinement")
        _t = time.time()
        process_all_json_files(
            OUTPUT_DIRECTORY,
            SEGMENTS_TO_REFINE,
            PROCESS_CODE_USING_LLM,
            PROCESS_FIGURES_USING_LLM,
        )
        logger.info("Step 5 completed in %.1fs", time.time() - _t)

    # 6. Insert page breaks in markdown files
    if should_run_step(6):
        log_step(6, "Inserting page breaks in markdown files")
        _t = time.time()
        insert_page_breaks_batch(OUTPUT_DIRECTORY)
        logger.info("Step 6 completed in %.1fs", time.time() - _t)

    # 7. Remove headers and footers from markdown files
    if should_run_step(7):
        log_step(7, "Removing headers and footers from markdown files")
        _t = time.time()
        remove_headers_footers_batch(OUTPUT_DIRECTORY)
        logger.info("Step 7 completed in %.1fs", time.time() - _t)

    # 8. Fix OCR errors in the markdown files
    if should_run_step(8):
        log_step(8, "Fixing OCR errors in markdown files")
        _t = time.time()
        fix_ocr_errors_batch(OUTPUT_DIRECTORY, RAW_PDF_TEXT_DIR)
        logger.info("Step 8 completed in %.1fs", time.time() - _t)

    # 9. Batch fix markdown section hierarchy using hierarchy JSON files
    if should_run_step(9):
        log_step(9, "Fixing markdown section hierarchy")
        _t = time.time()
        batch_fix_markdown_sections(HIERARCHY_JSON_DIRECTORY, OUTPUT_DIRECTORY)
        logger.info("Step 9 completed in %.1fs", time.time() - _t)

    # 10. Fix bullet point formatting in markdown files
    if should_run_step(10):
        log_step(10, "Standardizing bullet point formatting in markdown files")
        _t = time.time()
        fix_bullet_points_batch(OUTPUT_DIRECTORY)
        logger.info("Step 10 completed in %.1fs", time.time() - _t)

    total_time = time.time() - pipeline_start_time
    logger.info("=" * 80)
    logger.info("PDF Parsing Pipeline completed successfully!")
    logger.info(
        f"Total execution time: {timedelta(seconds=int(total_time))} ({total_time:.2f}s)"
    )
    logger.info("=" * 80)

    if _tmp_dir:
        shutil.rmtree(_tmp_dir, ignore_errors=True)
