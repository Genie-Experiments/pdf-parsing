import os
from pathlib import Path
from utils.get_markdown_file_path import get_markdown_file_path
from code_post_processing.search_code_in_markdown import search_code_in_markdown


def replace_code_in_markdown(original_code, cleaned_code, json_file_path):
    """
    Replace raw code content with cleaned/formatted code in the corresponding markdown file.
    
    Args:
        original_code (str): The original raw code content to be replaced
        cleaned_code (str): The cleaned/formatted code content to replace with
        json_file_path (str): Path to the JSON file to derive the markdown file path
    
    Returns:
        bool: True if replacement was successful, False otherwise
    """
    try:
        # First, find the exact location of the code in markdown
        search_result = search_code_in_markdown(original_code, json_file_path)
        
        if not search_result or not search_result['found']:
            print(f"  ✗ Original code content not found in markdown file")
            return False
        
        # Get markdown file path
        markdown_file_path = get_markdown_file_path(json_file_path)
        
        # Check if markdown file exists
        if not markdown_file_path.exists():
            print(f"  ✗ Markdown file not found: {markdown_file_path}")
            return False
        
        # Read the current markdown content
        with open(markdown_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract the exact matched text from the search result
        matched_text = search_result['matched_text']
        
        # Verify the matched text is still in the content (double-check)
        if matched_text not in content:
            print(f"  ✗ Matched code content no longer found in {markdown_file_path}")
            return False
        
        # Replace the matched text with cleaned code
        # Remove existing markdown code block wrapper if present in cleaned code
        if cleaned_code.startswith('```') and cleaned_code.endswith('```'):
            # Extract content between triple backticks
            lines = cleaned_code.split('\n')
            if len(lines) > 2:
                cleaned_content = '\n'.join(lines[1:-1])
            else:
                cleaned_content = cleaned_code
        else:
            cleaned_content = cleaned_code
        
        # Replace the original content with cleaned content
        updated_content = content.replace(matched_text, cleaned_content)
        
        # Write the updated content back to the file
        with open(markdown_file_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        print(f"  ✓ Successfully replaced code in {markdown_file_path}")
        print(f"    Line {search_result['line_number']}: {search_result['match_type']} match")
        return True
        
    except Exception as e:
        print(f"  ✗ Error replacing code in markdown: {str(e)}")
        return False


def replace_code_in_markdown_with_position(original_code, cleaned_code, json_file_path, 
                                         start_pos=None, end_pos=None):
    """
    Replace raw code content with cleaned code using specific position information.
    
    Args:
        original_code (str): The original raw code content
        cleaned_code (str): The cleaned/formatted code content to replace with
        json_file_path (str): Path to the JSON file
        start_pos (int, optional): Start position in markdown file
        end_pos (int, optional): End position in markdown file
    
    Returns:
        bool: True if replacement was successful, False otherwise
    """
    try:
        # Get markdown file path
        markdown_file_path = get_markdown_file_path(json_file_path)
        
        if not markdown_file_path.exists():
            print(f"  ✗ Markdown file not found: {markdown_file_path}")
            return False
        
        # Read the current markdown content
        with open(markdown_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # If positions are provided, use them directly
        if start_pos is not None and end_pos is not None:
            # Verify the positions are valid
            if start_pos < 0 or end_pos > len(content) or start_pos >= end_pos:
                print(f"  ✗ Invalid position range: {start_pos}-{end_pos}")
                return False
            
            # Extract content between the positions to verify it matches
            existing_text = content[start_pos:end_pos]
            
            # Remove markdown code wrapper if present in cleaned code
            if cleaned_code.startswith('```') and cleaned_code.endswith('```'):
                lines = cleaned_code.split('\n')
                if len(lines) > 2:
                    cleaned_content = '\n'.join(lines[1:-1])
                else:
                    cleaned_content = cleaned_code
            else:
                cleaned_content = cleaned_code
            
            # Perform the replacement
            updated_content = content[:start_pos] + cleaned_content + content[end_pos:]
            
            # Write back to file
            with open(markdown_file_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            
            print(f"  ✓ Successfully replaced code at position {start_pos}-{end_pos}")
            return True
        else:
            # Fall back to search-based replacement
            return replace_code_in_markdown(original_code, cleaned_code, json_file_path)
            
    except Exception as e:
        print(f"  ✗ Error replacing code in markdown: {str(e)}")
        return False