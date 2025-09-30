from process_pdf_files import process_pdf_files
from process_json_files import process_all_json_files

# Define paths
DATA_DIRECTORY = "./temp-test-data"  # Can now contain nested subdirectories with PDFs
OUTPUT_DIRECTORY = "./Results"  # Will maintain the same directory structure as input
DOLPHIN_SCRIPT = "./Dolphin/demo_page_hf.py"
MODEL_PATH = "./Dolphin/hf_model"

SEGMENTS_TO_EXTRACT = ["tab", "code"]

if __name__ == "__main__":
    # 1. Process PDF Files recursively from a directory
    #process_pdf_files(DATA_DIRECTORY, OUTPUT_DIRECTORY, DOLPHIN_SCRIPT, MODEL_PATH)

    # 2. Process all JSON files in results directory
    process_all_json_files(OUTPUT_DIRECTORY, SEGMENTS_TO_EXTRACT)

   