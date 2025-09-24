import json

def extract_segments(json_file_path, segments_to_extract:list):
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
                print(f"  Text/Content :\n{text}")

