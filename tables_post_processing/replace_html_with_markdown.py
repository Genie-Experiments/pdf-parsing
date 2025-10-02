import os
import re
from pathlib import Path
from utils.get_markdown_file_path import get_markdown_file_path

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
        markdown_file_path = get_markdown_file_path(json_file_path)
        
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
