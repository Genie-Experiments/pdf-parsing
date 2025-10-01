from process_pdf_files import process_pdf_files
from process_json_files import process_all_json_files

# Define paths
DATA_DIRECTORY = "./data"  # Directory containing PDFs (supports nested subdirectories)
OUTPUT_DIRECTORY = "./Results"  # Output directory (maintains same structure as input)
DOLPHIN_SCRIPT = "./Dolphin/demo_page_hf.py"
MODEL_PATH = "./Dolphin/hf_model"

# Configuration flags
PROCESS_CODE_USING_LLM = False  # Set to True to process code segments with LLM (GPT-4o Vision API)
                               # When True: Crops code sections from page images and uses OpenAI GPT-4o Vision
                               #           for high-quality code extraction and formatting
                               # When False: Uses traditional text-based code cleaning and formatting
                               # Requires OPENAI_API_KEY environment variable if enabled

SEGMENTS_TO_EXTRACT = ["tab", "code"]  # Supported: "tab" (tables), "code" (code blocks), "fig" (figures)

if __name__ == "__main__":
    # 1. Process PDF Files recursively from a directory
    # process_pdf_files(DATA_DIRECTORY, OUTPUT_DIRECTORY, DOLPHIN_SCRIPT, MODEL_PATH)

    # 2. Process all JSON files in results directory
    process_all_json_files(OUTPUT_DIRECTORY, SEGMENTS_TO_EXTRACT, PROCESS_CODE_USING_LLM)