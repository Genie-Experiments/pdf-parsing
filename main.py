import os
import time
from datetime import timedelta
from pathlib import Path

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

# Internal paths (not user-configurable)
DOLPHIN_SCRIPT = "./Dolphin/demo_page.py"
MODEL_PATH = "./Dolphin/hf_model"

# User-configurable settings
DATA_DIRECTORY = settings.data_directory
OUTPUT_DIRECTORY = settings.output_directory
PROCESS_CODE_USING_LLM = settings.process_code_using_llm
PROCESS_FIGURES_USING_LLM = settings.process_figures_using_llm
SEGMENTS_TO_REFINE = settings.segments_to_refine
RESUME = settings.resume
START_FROM_STEP = settings.start_from_step

# Derived pipeline dirs (consolidated under OUTPUT_DIRECTORY)
RAW_PDF_TEXT_DIR = os.path.join(OUTPUT_DIRECTORY, "_pipeline", "raw_text")
HIERARCHY_JSON_DIRECTORY = os.path.join(
    OUTPUT_DIRECTORY, "_pipeline", "section_hierarchy"
)


logger = get_logger(__name__)


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
    setup_logging(level="INFO", log_file="logs/pdf_parsing.log")

    pipeline_start_time = time.time()
    logger.info("Starting PDF Parsing Pipeline")
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
        process_pdf_files(DATA_DIRECTORY, OUTPUT_DIRECTORY, DOLPHIN_SCRIPT, MODEL_PATH)

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
        extract_all_pdf_texts(DATA_DIRECTORY, RAW_PDF_TEXT_DIR)

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
        batch_process_pdfs(
            data_directory=DATA_DIRECTORY,
            output_base_dir=HIERARCHY_JSON_DIRECTORY,
            min_heading_size=12,
            max_levels=6,
            bold_only=False,
            exclude_headers_footers=True,
        )

    # 4. Create backup of markdown files before post-processing
    if should_run_step(4):
        log_step(4, "Creating backup of markdown files before post-processing")
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

    # 5. Process all JSON files in results directory
    if should_run_step(5):
        log_step(5, "Processing JSON files for segment refinement")
        process_all_json_files(
            OUTPUT_DIRECTORY,
            SEGMENTS_TO_REFINE,
            PROCESS_CODE_USING_LLM,
            PROCESS_FIGURES_USING_LLM,
        )

    # 6. Insert page breaks in markdown files
    if should_run_step(6):
        log_step(6, "Inserting page breaks in markdown files")
        insert_page_breaks_batch(OUTPUT_DIRECTORY)

    # 7. Remove headers and footers from markdown files
    if should_run_step(7):
        log_step(7, "Removing headers and footers from markdown files")
        remove_headers_footers_batch(OUTPUT_DIRECTORY)

    # 8. Fix OCR errors in the markdown files
    if should_run_step(8):
        log_step(8, "Fixing OCR errors in markdown files")
        fix_ocr_errors_batch(OUTPUT_DIRECTORY, RAW_PDF_TEXT_DIR)

    # 9. Batch fix markdown section hierarchy using hierarchy JSON files
    if should_run_step(9):
        log_step(9, "Fixing markdown section hierarchy")
        batch_fix_markdown_sections(HIERARCHY_JSON_DIRECTORY, OUTPUT_DIRECTORY)

    # 10. Fix bullet point formatting in markdown files
    if should_run_step(10):
        log_step(10, "Standardizing bullet point formatting in markdown files")
        fix_bullet_points_batch(OUTPUT_DIRECTORY)

    total_time = time.time() - pipeline_start_time
    logger.info("=" * 80)
    logger.info("PDF Parsing Pipeline completed successfully!")
    logger.info(
        f"Total execution time: {timedelta(seconds=int(total_time))} ({total_time:.2f}s)"
    )
    logger.info("=" * 80)
