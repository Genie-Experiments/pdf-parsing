import crop_pdf_regions
from process_pdf_files import process_pdf_files
from process_json_files import process_all_json_files
from crop_pdf_regions import create_bbox_adjustment_test
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
    process_pdf_files(DATA_DIRECTORY, OUTPUT_DIRECTORY, DOLPHIN_SCRIPT, MODEL_PATH)

    # 2. Process all JSON files in results directory
    #process_all_json_files(OUTPUT_DIRECTORY, SEGMENTS_TO_EXTRACT)

    # crop_pdf_regions usage example (uncomment to use)
    # # Extract as cropped PDFs
    #boxes = [528, 140, 869, 571]

    #boxes = [131, 561, 633, 647]
    
    #pdf_file = "./temp-test-dir/Extreme_AirDefense_Essentials_v23r3_Release_Notes.pdf"
    # # pdf_file = "./test-data/page-21.pdf"

    # out_pdf = crop_pdf_with_margin_adjustment(pdf_file, boxes, output_prefix="output/crop_table", page_number = 3, as_image=False)
    # print("Cropped PDF:", out_pdf)

    # out_img = crop_pdf_with_margin_adjustment(pdf_file, boxes, output_prefix="output/crop_table", page_number = 3, as_image=True)
    # print("Cropped Image:", out_img)

    #simple_coordinate_test(pdf_file, boxes, page_number=3)

    # This should work better based on your debug image
# result = auto_crop_pdf_table(
#     pdf_path=pdf_file,
#     bbox=boxes,
#     output_prefix="output/table_auto_fixed",
#     page_number=3,
#     as_image=True,
#     debug=True
# )

#     create_bbox_adjustment_test(
#     pdf_path=pdf_file, 
#     bbox=boxes,
#     page_number=3
# )

#     # 3. Convert HTML to Markdown
#     html_text = "<table><tr><td>ID</td><td>Description</td></tr><tr><td>02434953</td><td>Extreme AirDefense Essentials might generate false rogue AP alarms</td></tr><tr><td>02590366</td><td>due to incorrectly identifying neighboring Extreme Networks AP</td></tr><tr><td>02666601</td><td>devices using the same network policy as rogue APs.</td></tr></table>"

#     result = convert_html_to_markdown(
#     html_text, 
#     enable_all_plugins=True
# )

#     print (result)