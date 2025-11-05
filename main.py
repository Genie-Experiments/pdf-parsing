from process_pdf_files.process_pdf_files import process_pdf_files
from post_processing.process_json_files import process_all_json_files
from post_processing.markdown_sections_post_processing.fix_markdown_sections import fix_markdown_headings, batch_fix_markdown_sections
from post_processing.markdown_sections_post_processing.section_hierarchy_from_pdf import batch_process_pdfs
from post_processing.fix_ocr_errors.get_text_from_pdf import extract_all_pdf_texts
from post_processing.fix_ocr_errors.fix_ocr_errors import fix_ocr_errors_batch
from post_processing.remove_headers_and_footers.insert_page_breaks import insert_page_breaks_batch
from post_processing.remove_headers_and_footers.remove_headers_footers import remove_headers_footers_batch
from post_processing.fix_bullet_points.fix_bullet_points import fix_bullet_points_batch
from utils.create_backups_md import create_markdown_backup
from utils.logger import setup_logging, get_logger, log_step
from config.config import settings

# Import configuration settings
DATA_DIRECTORY = settings.data_directory
OUTPUT_DIRECTORY = settings.output_directory
DOLPHIN_SCRIPT = settings.dolphin_script
MODEL_PATH = settings.model_path
HIERARCHY_JSON_DIRECTORY = settings.hierarchy_json_directory
PROCESS_CODE_USING_LLM = settings.process_code_using_llm
PROCESS_FIGURES_USING_LLM = settings.process_figures_using_llm
SEGMENTS_TO_REFINE = settings.segments_to_refine
RAW_PDF_TEXT_DIR = settings.raw_pdf_text_dir

if __name__ == "__main__":
    # Setup logging system
    setup_logging(level='INFO', log_file='logs/pdf_parsing.log')
    logger = get_logger(__name__)
    
    logger.info("Starting PDF Parsing Pipeline")

    # # 1. Process PDF Files recursively from a directory
    # log_step(1, "Processing PDF files for extracting base line markdown with Dolphin model")
    # process_pdf_files(DATA_DIRECTORY, OUTPUT_DIRECTORY, DOLPHIN_SCRIPT, MODEL_PATH)

    # logger.info("Starting Post-Processing Steps...")
    
    # Post-Processing Steps

    # 2. Extract raw text from all PDF files
    # log_step(2, f"Extracting raw text from all PDF files and storing them in {RAW_PDF_TEXT_DIR} folder")
    # extract_all_pdf_texts(DATA_DIRECTORY, RAW_PDF_TEXT_DIR)
    
    # # 3. Generate section hierarchy JSONs from PDFs
    # log_step(3, "Generating section hierarchy JSONs from PDFs")
    # batch_process_pdfs(
    #     data_directory=DATA_DIRECTORY,
    #     output_base_dir=HIERARCHY_JSON_DIRECTORY,
    #     min_heading_size=12, # or set to None to auto-detect
    #     max_levels=6,
    #     bold_only=False,
    #     exclude_headers_footers=True
    # )

    # 4. Create backup of markdown files before post-processing
    log_step(4, "Creating backup of markdown files before post-processing")
    backup_count = create_markdown_backup(OUTPUT_DIRECTORY)
    if backup_count:
        logger.info("Successfully created %d backup files with '_backup' suffix", backup_count)
    else:
        logger.info("No markdown files found to backup, continuing with post-processing...")

    # 5. Process all JSON files in results directory
    log_step(5, "Processing JSON files for segment refinement")
    process_all_json_files(OUTPUT_DIRECTORY, SEGMENTS_TO_REFINE, PROCESS_CODE_USING_LLM, PROCESS_FIGURES_USING_LLM)

    # 6. Insert page breaks in markdown files
    log_step(6, "Inserting page breaks in markdown files")
    insert_page_breaks_batch(OUTPUT_DIRECTORY)

    # 7. Remove headers and footers from markdown files
    log_step(7, "Removing headers and footers from markdown files")
    remove_headers_footers_batch(OUTPUT_DIRECTORY)

    # 8. Fix OCR errors in the markdown files
    log_step(8, "Fixing OCR errors in markdown files")
    fix_ocr_errors_batch(OUTPUT_DIRECTORY, RAW_PDF_TEXT_DIR)

    # 9. Batch fix markdown section hierarchy using hierarchy JSON files
    log_step(9, "Fixing markdown section hierarchy")
    batch_fix_markdown_sections(HIERARCHY_JSON_DIRECTORY, OUTPUT_DIRECTORY)

    # 10. Fix bullet point formatting in markdown files
    log_step(10, "Standardizing bullet point formatting in markdown files")
    fix_bullet_points_batch(OUTPUT_DIRECTORY)
    
    logger.info("PDF Parsing Pipeline completed successfully!")
