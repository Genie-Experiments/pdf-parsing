import os
import re
from pathlib import Path

def replace_html_with_markdown(original_html, markdown_text, json_file_path):
    """
    Replace HTML table content with markdown in the corresponding markdown file.
    
    Args:
        original_html (str): The original HTML content to be replaced
        markdown_text (str): The markdown content to replace with
        json_file_path (str): Path to the JSON file to derive the markdown file path
    
    Returns:
        bool: True if replacement was successful, False otherwise
    """
    try:
        # Extract the markdown file path from JSON file path
        # Example: results/page-04/recognition_json/page-04.json -> results/page-04/markdown/page-04.md
        json_path = Path(json_file_path)
        
        # Get the parent directory (e.g., results/page-04)
        parent_dir = json_path.parent.parent
        
        # Get the base filename without extension (e.g., page-04)
        base_filename = json_path.stem
        
        # Construct the markdown file path
        markdown_file_path = parent_dir / "markdown" / f"{base_filename}.md"
        
        # Check if markdown file exists
        if not markdown_file_path.exists():
            print(f"  ✗ Markdown file not found: {markdown_file_path}")
            return False
        
        # Read the current markdown content
        with open(markdown_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if the original HTML content exists in the file
        if original_html not in content:
            print(f"  ✗ Original HTML content not found in {markdown_file_path}")
            return False
        
        # Replace the HTML content with markdown
        updated_content = content.replace(original_html, markdown_text)
        
        # Write the updated content back to the file
        with open(markdown_file_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        print(f"  ✓ Successfully replaced HTML with markdown in {markdown_file_path}")
        return True
        
    except Exception as e:
        print(f"  ✗ Error replacing HTML with markdown: {str(e)}")
        return False



# # optional advanced function with regex support, we are not using it currently
# def replace_html_with_markdown_by_pattern(original_html, markdown_text, json_file_path, use_regex=False):
#     """
#     Replace HTML table content with markdown using pattern matching (optional regex support).
#     This is useful when the HTML content might have slight variations or whitespace differences.
    
#     Args:
#         original_html (str): The original HTML content to be replaced
#         markdown_text (str): The markdown content to replace with
#         json_file_path (str): Path to the JSON file to derive the markdown file path
#         use_regex (bool): Whether to use regex for pattern matching
    
#     Returns:
#         bool: True if replacement was successful, False otherwise
#     """
#     try:
#         # Extract the markdown file path from JSON file path
#         json_path = Path(json_file_path)
#         parent_dir = json_path.parent.parent
#         base_filename = json_path.stem
#         markdown_file_path = parent_dir / "markdown" / f"{base_filename}.md"
        
#         if not markdown_file_path.exists():
#             print(f"  ✗ Markdown file not found: {markdown_file_path}")
#             return False
        
#         # Read the current markdown content
#         with open(markdown_file_path, 'r', encoding='utf-8') as f:
#             content = f.read()
        
#         if use_regex:
#             # Escape special regex characters in the HTML content
#             escaped_html = re.escape(original_html)
#             # Allow for flexible whitespace matching
#             flexible_pattern = escaped_html.replace(r'\ ', r'\s*').replace(r'\>', r'>\s*').replace(r'\<', r'\s*<')
            
#             # Use regex substitution
#             updated_content = re.sub(flexible_pattern, markdown_text, content, flags=re.IGNORECASE | re.DOTALL)
            
#             if updated_content == content:
#                 print(f"  ✗ Original HTML pattern not found in {markdown_file_path}")
#                 return False
#         else:
#             # Use simple string replacement
#             if original_html not in content:
#                 print(f"  ✗ Original HTML content not found in {markdown_file_path}")
#                 return False
#             updated_content = content.replace(original_html, markdown_text)
        
#         # Write the updated content back to the file
#         with open(markdown_file_path, 'w', encoding='utf-8') as f:
#             f.write(updated_content)
        
#         print(f"  ✓ Successfully replaced HTML with markdown in {markdown_file_path}")
#         return True
        
#     except Exception as e:
#         print(f"  ✗ Error replacing HTML with markdown: {str(e)}")
#         return False
