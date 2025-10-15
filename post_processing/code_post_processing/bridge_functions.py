"""
Bridge functions to maintain compatibility between old and new code_post_processing modules.
These functions provide the same API as the old module while using the new implementation.
"""

from pathlib import Path
from typing import Dict, Optional, Any
from utils.get_markdown_file_path import get_markdown_file_path
from post_processing.code_post_processing.markdown_code_replacer import find_code_in_markdown, replace_cleaned_with_original_code
from post_processing.code_post_processing.clean_and_format_code import clean_and_format_code as new_clean_and_format_code


def search_code_in_markdown(json_code_text: str, json_file_path: str) -> Dict[str, Any]:
    """
    Bridge function that mimics the old search_code_in_markdown API.
    
    Args:
        json_code_text: The raw code text from JSON to search for
        json_file_path: Path to the JSON file
        
    Returns:
        Dictionary with search results matching old API format
    """
    try:
        # Get markdown file path
        markdown_file_path = get_markdown_file_path(json_file_path)
        
        # Check if markdown file exists
        if not markdown_file_path.exists():
            return {
                'found': False,
                'error': f'Markdown file not found: {markdown_file_path}'
            }
        
        # Read markdown content
        with open(markdown_file_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
        
        # Clean and format the code first
        cleaned_code = new_clean_and_format_code(json_code_text)
        
        # Use the new function to find code in markdown
        found_text, start_line, end_line = find_code_in_markdown(markdown_content, cleaned_code)
        
        if found_text is not None:
            return {
                'found': True,
                'matched_text': found_text,
                'line_number': start_line,
                'start_line': start_line,
                'end_line': end_line,
                'match_type': 'fuzzy'  # The new implementation uses fuzzy matching
            }
        else:
            return {
                'found': False,
                'error': 'Code not found in markdown file'
            }
            
    except Exception as e:
        return {
            'found': False,
            'error': f'Error searching code in markdown: {str(e)}'
        }


def replace_code_in_markdown(original_code: str, cleaned_code: str, json_file_path: str) -> bool:
    """
    Bridge function that mimics the old replace_code_in_markdown API.
    
    Args:
        original_code: The original raw code content to be replaced
        cleaned_code: The cleaned/formatted code content to replace with
        json_file_path: Path to the JSON file
        
    Returns:
        Boolean indicating success
    """
    try:
        # Get markdown file path
        markdown_file_path = get_markdown_file_path(json_file_path)
        
        # Check if markdown file exists
        if not markdown_file_path.exists():
            print(f"  ✗ Markdown file not found: {markdown_file_path}")
            return False
        
        # Read markdown content
        with open(markdown_file_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
        
        # Find the code in markdown using the new implementation
        found_text, start_line, end_line = find_code_in_markdown(markdown_content, cleaned_code)
        
        if found_text is None:
            print(f"  ✗ Code content not found in markdown file")
            return False
        
        # Replace the found text with the cleaned code
        updated_content = markdown_content.replace(found_text, cleaned_code, 1)
        
        # Write back to the file
        with open(markdown_file_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error replacing code in markdown: {str(e)}")
        return False


def clean_and_format_code(raw_text: str) -> str:
    """
    Bridge function for clean_and_format_code - direct passthrough since API is the same.
    """
    return new_clean_and_format_code(raw_text)


# Optional: Enhanced replacement function that uses the full capability of the new module
def replace_code_with_pdf_original(json_file_path: str, pdf_file_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Enhanced function that replaces cleaned code with original PDF code.
    This uses the full capability of the new module.
    
    Args:
        json_file_path: Path to the JSON file
        pdf_file_path: Path to the PDF file (optional, will try to infer if not provided)
        
    Returns:
        Dictionary with replacement results
    """
    try:
        # Get markdown file path
        markdown_file_path = get_markdown_file_path(json_file_path)
        
        # Try to infer PDF path if not provided
        if pdf_file_path is None:
            # Try to find PDF file based on JSON file path structure
            json_path = Path(json_file_path)
            # Look for PDF file in Data directory with same base name
            possible_pdf_paths = []
            
            # Get the document name from the JSON file path
            # Assuming structure: Results/.../recognition_json/document_name.json
            document_name = json_path.stem
            
            # Look in Data directory
            data_dir = json_path.parent.parent.parent / "Data"
            if data_dir.exists():
                for pdf_file in data_dir.rglob(f"{document_name}.pdf"):
                    possible_pdf_paths.append(str(pdf_file))
            
            if possible_pdf_paths:
                pdf_file_path = possible_pdf_paths[0]
            else:
                return {
                    'success': False,
                    'error': 'Could not find corresponding PDF file'
                }
        
        # Use the new comprehensive replacement function
        results = replace_cleaned_with_original_code(
            str(markdown_file_path), 
            pdf_file_path, 
            json_file_path
        )
        
        return {
            'success': results.get('successful_replacements', 0) > 0,
            'results': results
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f'Error in enhanced replacement: {str(e)}'
        }