from process_pdf_files import process_pdf_files
from process_json_files import process_all_json_files
from fix_markdown_sections import fix_markdown_headings, batch_fix_markdown_sections

# Define paths
DATA_DIRECTORY = "./data"  # Directory containing PDFs (supports nested subdirectories)
OUTPUT_DIRECTORY = "./Results"  # Output directory (maintains same structure as input)
DOLPHIN_SCRIPT = "./Dolphin/demo_page_hf.py"
MODEL_PATH = "./Dolphin/hf_model"
TOC_JSON_DIRECTORY = "./toc_json_files"  # Directory containing TOC JSON files with section hierarchy

# Configuration flags
PROCESS_CODE_USING_LLM = False  # Set to True to process code segments with LLM (GPT-4o Vision API)
                               # When True: Crops code sections from page images and uses OpenAI GPT-4o Vision
                               #           for high-quality code extraction and formatting
                               # When False: Uses traditional text-based code cleaning and formatting
                               # Requires OPENAI_API_KEY environment variable if enabled

PROCESS_FIGURES_USING_LLM = False  # Set to True to process figure segments with LLM (GPT-4o Vision API)

SEGMENTS_TO_REFINE = ["tab", "code", "fig"]  # Supported: "tab" (tables), "code" (code blocks), "fig" (figures)

if __name__ == "__main__":
    # 1. Process PDF Files recursively from a directory
    # process_pdf_files(DATA_DIRECTORY, OUTPUT_DIRECTORY, DOLPHIN_SCRIPT, MODEL_PATH)

    # 2. Process all JSON files in results directory
    process_all_json_files(OUTPUT_DIRECTORY, SEGMENTS_TO_REFINE, PROCESS_CODE_USING_LLM, PROCESS_FIGURES_USING_LLM)

    # 3. Batch fix markdown section hierarchy using TOC JSON files
    #batch_fix_markdown_sections(TOC_JSON_DIRECTORY, OUTPUT_DIRECTORY)
