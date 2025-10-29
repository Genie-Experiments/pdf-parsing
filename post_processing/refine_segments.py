import json
from post_processing.code_post_processing.handle_code_element import handle_code_element
from post_processing.figures_post_processing.handle_figure_element import handle_figure_element
from post_processing.tables_post_processing.handle_table_element import handle_table_element

def refine_segments(json_file_path, segments_to_extract:list, process_code_using_llm=False, process_figures_using_llm=False):
    # Load the recognition.json file
    with open(json_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Loop through pages and elements
    for page in data.get("pages", []):
        page_number = page.get("page_number")
        print(f"\n--- Page {page_number} ---")

        for element in page.get("elements", []):
            label = element.get("label")

            if label in segments_to_extract:  # check for specified segments
                bbox = element.get("bbox")
                text = element.get("text")
                reading_order = element.get("reading_order")

                print(f"\nFound {label.upper()}:")
                print(f"  Bounding Box : {bbox}")
                print(f"  Reading Order: {reading_order}")
                
                # Special handling for table elements
                if label == "tab":
                    handle_table_element(text, json_file_path)
                    
                # Special handling for code elements
                elif label == "code":
                    handle_code_element(text, json_file_path, page_number, bbox, reading_order, label)
                
                # Special handling for figure elements
                elif label == "fig" and process_figures_using_llm:
                    handle_figure_element(text, element, page, json_file_path)

                    