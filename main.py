from process_pdf_files.process_pdf_files import process_pdf_files
from post_processing.process_json_files import process_all_json_files
from post_processing.markdown_sections_post_processing.fix_markdown_sections import fix_markdown_headings, batch_fix_markdown_sections
import config.config as config

# Import configuration settings
DATA_DIRECTORY = config.DATA_DIRECTORY
OUTPUT_DIRECTORY = config.OUTPUT_DIRECTORY
DOLPHIN_SCRIPT = config.DOLPHIN_SCRIPT
MODEL_PATH = config.MODEL_PATH
TOC_JSON_DIRECTORY = config.TOC_JSON_DIRECTORY
PROCESS_CODE_USING_LLM = config.PROCESS_CODE_USING_LLM
PROCESS_FIGURES_USING_LLM = config.PROCESS_FIGURES_USING_LLM
SEGMENTS_TO_REFINE = config.SEGMENTS_TO_REFINE

if __name__ == "__main__":
    # 1. Process PDF Files recursively from a directory
    #process_pdf_files(DATA_DIRECTORY, OUTPUT_DIRECTORY, DOLPHIN_SCRIPT, MODEL_PATH)

    # 2. Process all JSON files in results directory
    process_all_json_files(OUTPUT_DIRECTORY, SEGMENTS_TO_REFINE, PROCESS_CODE_USING_LLM, PROCESS_FIGURES_USING_LLM)

    # 3. Batch fix markdown section hierarchy using TOC JSON files
    batch_fix_markdown_sections(TOC_JSON_DIRECTORY, OUTPUT_DIRECTORY)
