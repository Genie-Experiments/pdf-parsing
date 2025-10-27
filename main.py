from process_pdf_files.process_pdf_files import process_pdf_files
from post_processing.process_json_files import process_all_json_files
from post_processing.markdown_sections_post_processing.fix_markdown_sections import fix_markdown_headings, batch_fix_markdown_sections
from post_processing.markdown_sections_post_processing.section_hierarchy_from_pdf import batch_process_pdfs
from post_processing.fix_ocr_errors.get_text_from_pdf import extract_all_pdf_texts
from post_processing.fix_ocr_errors.fix_ocr_errors import fix_ocr_errors_batch
from post_processing.remove_headers_and_footers.insert_page_breaks import insert_page_breaks_batch
from post_processing.remove_headers_and_footers.remove_headers_footers import remove_headers_footers_batch
from utils.create_backups_md import create_markdown_backup
import config.config as config

# Import configuration settings
DATA_DIRECTORY = config.DATA_DIRECTORY
OUTPUT_DIRECTORY = config.OUTPUT_DIRECTORY
DOLPHIN_SCRIPT = config.DOLPHIN_SCRIPT
MODEL_PATH = config.MODEL_PATH
HIERARCHY_JSON_DIRECTORY = config.HIERARCHY_JSON_DIRECTORY
PROCESS_CODE_USING_LLM = config.PROCESS_CODE_USING_LLM
PROCESS_FIGURES_USING_LLM = config.PROCESS_FIGURES_USING_LLM
SEGMENTS_TO_REFINE = config.SEGMENTS_TO_REFINE
RAW_PDF_TEXT_DIR = config.RAW_PDF_TEXT_DIR

if __name__ == "__main__":

    # 1. Process PDF Files recursively from a directory
    print("\n" + "="*60)
    print("STEP 1: Processing PDF files for extracting base line markdown with Dolphin model")
    print("="*60)
    process_pdf_files(DATA_DIRECTORY, OUTPUT_DIRECTORY, DOLPHIN_SCRIPT, MODEL_PATH)

    # print ("\n" + "="*60)
    # print("Starting Post-Processing Steps.....")
    
    # # Post-Processing Steps

    # # 2. Extract raw text from all PDF files
    # print("="*60)
    # print("STEP 2: Extracting raw text from all PDF files and storing them in {RAW_PDF_TEXT_DIR} folder")
    # print("="*60)
    # extract_all_pdf_texts(DATA_DIRECTORY, RAW_PDF_TEXT_DIR)
    
    # # # 3. Generate section hierarchy JSONs from PDFs
    # print("\n" + "="*60)
    # print("STEP 3: Generating section hierarchy JSONs from PDFs")
    # print("="*60)
    # batch_process_pdfs(
    #     data_directory=DATA_DIRECTORY,
    #     output_base_dir=HIERARCHY_JSON_DIRECTORY,
    #     min_heading_size=12, # or set to None to auto-detect
    #     max_levels=6,
    #     bold_only=False,
    #     exclude_headers_footers=True
    # )

    # # 4. Create backup of markdown files before post-processing
    # print("\n" + "="*60)
    # print("STEP 4: Creating backup of markdown files before post-processing")
    # print("="*60)
    # backup_count = create_markdown_backup(OUTPUT_DIRECTORY)
    # if backup_count:
    #     print(f"Successfully created {backup_count} backup files with '_backup' suffix")
    # else:
    #     print("No markdown files found to backup, continuing with post-processing...")

    # # 5. Process all JSON files in results directory
    # print("\n" + "="*60)
    # print("STEP 5: Processing JSON files for segment refinement")
    # print("="*60)
    # process_all_json_files(OUTPUT_DIRECTORY, SEGMENTS_TO_REFINE, PROCESS_CODE_USING_LLM, PROCESS_FIGURES_USING_LLM)

    # # 6. Insert page breaks in markdown files
    # print("\n" + "="*60)
    # print("STEP 6: Inserting page breaks in markdown files")
    # print("="*60)
    # insert_page_breaks_batch(OUTPUT_DIRECTORY)

    # # 7. Remove headers and footers from markdown files
    # print("\n" + "="*60)
    # print("STEP 7: Removing headers and footers from markdown files")
    # print("="*60)
    # remove_headers_footers_batch(OUTPUT_DIRECTORY)

    # # 8. Fix OCR errors in the markdown files
    # print("\n" + "="*60)
    # print("STEP 8: Fixing OCR errors in markdown files")
    # print("="*60)
    # fix_ocr_errors_batch(OUTPUT_DIRECTORY, RAW_PDF_TEXT_DIR)


    # # 9. Batch fix markdown section hierarchy using hierarchy JSON files
    # print("\n" + "="*60)
    # print("STEP 9: Fixing markdown section hierarchy")
    # print("="*60)
    # # batch_fix_markdown_sections(HIERARCHY_JSON_DIRECTORY, OUTPUT_DIRECTORY)

    