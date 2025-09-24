#import crop_pdf_regions
from process_pdf_files import process_pdf_files
from process_json_files import process_all_json_files
#from crop_pdf_regions import create_bbox_adjustment_test
#from test import simple_coordinate_test

from convert_html_to_markdown import convert_html_to_markdown


# Define paths
DATA_DIRECTORY = "./temp-test-dir"
OUTPUT_DIRECTORY = "./results"
DOLPHIN_SCRIPT = "./Dolphin/demo_page_hf.py"
MODEL_PATH = "./Dolphin/hf_model"

SEGMENTS_TO_EXTRACT = ["tab", "code", "fig"]

if __name__ == "__main__":
    # 1. Process PDF Files from a directory
    #process_pdf_files(DATA_DIRECTORY, OUTPUT_DIRECTORY, DOLPHIN_SCRIPT, MODEL_PATH)

    # 2. Process all JSON files in results directory
    process_all_json_files(OUTPUT_DIRECTORY, SEGMENTS_TO_EXTRACT)

   