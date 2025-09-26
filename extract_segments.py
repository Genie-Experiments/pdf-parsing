import json
from convert_html_to_markdown import convert_html_to_markdown
from replace_html_with_markdown import replace_html_with_markdown

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
                
                # Special handling for table elements
                if label == "tab":
                    print(f"  HTML Content :\n{text}")
                    
                    # Convert HTML table to markdown
                    markdown_content = convert_html_to_markdown(text, enable_table_plugin=True, verbose=True)
                    
                    if markdown_content:
                        print(f"\n  Converted to Markdown:")
                        print(f"  {'-' * 40}")
                        print(markdown_content)
                        print(f"  {'-' * 40}")
                        
                        # Replace HTML with markdown in the corresponding markdown file
                        print(f"\n  Replacing HTML with markdown in file...")
                        success = replace_html_with_markdown(text, markdown_content, json_file_path)
                        
                        if success:
                            print(f"  ✓ HTML table successfully replaced with markdown!")
                        else:
                            print(f"  ✗ Failed to replace HTML with markdown")
                    else:
                        print("  Failed to convert HTML to markdown")
                else:
                    print(f"  Text/Content :\n{text}")

