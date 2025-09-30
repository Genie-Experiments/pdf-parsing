import json
from convert_html_to_markdown import convert_html_to_markdown
from utils.replace_html_with_markdown import replace_html_with_markdown
from utils.clean_and_format_code import clean_and_format_code
from utils.search_code_in_markdown import search_code_in_markdown
from utils.replace_code_in_markdown import replace_code_in_markdown
from utils.process_figure import (
    get_figure_info_and_context, 
    generate_figure_description, 
    search_and_replace_figure_in_markdown
)

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
                
                # Special handling for code elements
                elif label == "code":
                    print(f"  Raw Code Content :\n{text}")
                    
                    # Clean and format the raw code
                    cleaned_code = clean_and_format_code(text)
                    
                    if cleaned_code:
                        print(f"\n  Cleaned and Formatted Code:")
                        print(f"  {'-' * 40}")
                        print(cleaned_code)
                        print(f"  {'-' * 40}")
                        
                        # Search for the raw code in the markdown file
                        print(f"\n  Searching for raw code in markdown file...")
                        search_result = search_code_in_markdown(text, json_file_path)
                        
                        if search_result and search_result['found']:
                            print(f"  ✓ Found code at line {search_result['line_number']} ({search_result['match_type']} match)")
                            
                            # Replace the raw code with cleaned code in markdown
                            print(f"\n  Replacing raw code with cleaned code...")
                            success = replace_code_in_markdown(text, cleaned_code, json_file_path)
                            
                            if success:
                                print(f"  ✓ Raw code successfully replaced with cleaned code!")
                            else:
                                print(f"  ✗ Failed to replace raw code with cleaned code")
                        else:
                            print(f"  ✗ Raw code not found in markdown file - cannot replace")
                    else:
                        print("  ✗ Failed to clean and format code")
                
                # Special handling for figure elements
                elif label == "fig":
                    print(f"  Figure Text/Reference :\n{text}")
                    
                    # Get figure information and context
                    print(f"\n  Extracting figure information and context...")
                    figure_info = get_figure_info_and_context(element, page.get("elements", []), json_file_path)
                    
                    if figure_info["image_exists"]:
                        print(f"  ✓ Figure image found: {figure_info['relative_figure_path']}")
                        print(f"  Context length: {len(figure_info['context_text'])} characters")
                        
                        # Generate figure description using LLM
                        print(f"\n  Generating figure description using LLM...")
                        description = generate_figure_description(
                            figure_info["figure_path"], 
                            figure_info["context_text"]
                        )
                        
                        if description:
                            print(f"\n  Generated Description:")
                            print(f"  {'-' * 40}")
                            print(description)
                            print(f"  {'-' * 40}")
                            
                            # Replace figure text with description in markdown
                            print(f"\n  Replacing figure text with description in markdown...")
                            success = search_and_replace_figure_in_markdown(
                                figure_info["figure_text"], 
                                description, 
                                json_file_path
                            )
                            
                            if success:
                                print(f"  ✓ Figure text successfully replaced with description!")
                            else:
                                print(f"  ✗ Failed to replace figure text with description")
                        else:
                            print("  ✗ Failed to generate figure description")
                    else:
                        print(f"  ✗ Figure image not found: {figure_info['relative_figure_path']}")
                        print(f"  Expected path: {figure_info['figure_path']}")
                
                else:
                    print(f"  Text/Content :\n{text}")

