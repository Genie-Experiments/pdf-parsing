from convert_html_to_markdown import convert_html_to_markdown
from replace_html_with_markdown import replace_html_with_markdown

def handle_table_element(text, json_file_path):

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
  
