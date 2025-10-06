import json
from tables_post_processing.convert_html_to_markdown import convert_html_to_markdown
from tables_post_processing.replace_html_with_markdown import replace_html_with_markdown
from code_post_processing.clean_and_format_code import clean_and_format_code
from code_post_processing.search_code_in_markdown import search_code_in_markdown
from code_post_processing.replace_code_in_markdown import replace_code_in_markdown
from figures_post_processing.process_figure import (
    get_figure_info_and_context, 
    generate_figure_description, 
    search_and_replace_figure_in_markdown
)
from code_post_processing.process_code_with_llm import process_code_with_llm
from config.config import DATA_DIRECTORY
import os
from pathlib import Path

def get_context_for_code_element(json_data, code_element, page_data, context_window=2):
    """
    Extract contextual text from elements surrounding a code block.
    
    Args:
        json_data: Full JSON data from the document
        code_element: The code element we're looking for context around
        page_data: The page data containing this code element
        context_window: Number of elements before the code to include as context
        
    Returns:
        String containing contextual text from surrounding elements
    """
    try:
        target_reading_order = code_element.get('reading_order')
        
        # Use the provided page data directly
        target_page = page_data
        
        if not target_page:
            return ""
        
        # Get elements from the same page, sorted by reading order
        page_elements = sorted(
            target_page.get('elements', []), 
            key=lambda x: x.get('reading_order', 0)
        )
        
        # Find the index of our code element
        code_index = -1
        for i, element in enumerate(page_elements):
            if (element.get('reading_order') == target_reading_order and 
                element.get('label') == 'code'):
                code_index = i
                break
        
        if code_index == -1:
            return ""
        
        # Extract context from elements BEFORE the code (more important for context)
        context_texts = []
        start_idx = max(0, code_index - context_window)
        
        for i in range(start_idx, code_index):
            element = page_elements[i]
            label = element.get('label', '')
            text = element.get('text', '').strip()
            
            # Include text from paragraphs, headers, titles, and list items
            if label in ['para', 'header', 'title', 'list'] and text:
                # Clean up the text (remove excessive whitespace, but keep structure)
                cleaned_text = ' '.join(text.split())
                if cleaned_text:
                    context_texts.append(cleaned_text)
        
        # Join context texts with space
        context = ' '.join(context_texts)
        
        # Limit context length to avoid too much noise
        if len(context) > 500:
            context = context[:500] + "..."
        
        return context
        
    except Exception as e:
        print(f"  ⚠ Error extracting context: {str(e)}")
        return ""

def list_all_pdfs_in_config_directories(project_root_path=None):
    """
    List all PDF files found in the configured directories for debugging purposes.
    
    Args:
        project_root_path: Optional project root path. If not provided, uses current working directory.
        
    Returns:
        Dictionary with directory paths as keys and lists of PDF files as values
    """
    if project_root_path is None:
        project_root_path = Path.cwd()
    else:
        project_root_path = Path(project_root_path)
    
    directories_to_search = [DATA_DIRECTORY]
    pdf_inventory = {}
    
    print(f"📋 PDF Inventory for configured directories:")
    print(f"   Project root: {project_root_path}")
    
    for directory in directories_to_search:
        # Handle both relative and absolute paths
        if not os.path.isabs(directory):
            search_path = project_root_path / directory.lstrip('./')
        else:
            search_path = Path(directory)
        
        pdf_files = []
        if search_path.exists():
            pdf_files = [str(pdf) for pdf in search_path.rglob("*.pdf")]
            pdf_files.sort()
        
        pdf_inventory[str(search_path)] = pdf_files
        
        print(f"\n📁 {directory} -> {search_path}")
        if search_path.exists():
            print(f"   Status: ✅ Directory exists")
            print(f"   PDFs found: {len(pdf_files)}")
            if pdf_files:
                for pdf in pdf_files[:5]:  # Show first 5 PDFs
                    print(f"     • {Path(pdf).name}")
                if len(pdf_files) > 5:
                    print(f"     ... and {len(pdf_files) - 5} more")
        else:
            print(f"   Status: ❌ Directory not found")
    
    return pdf_inventory

def get_pdf_file_path(json_file_path):
    """
    Find the corresponding PDF file using recursive search in the configured PDF directories.
    Searches the primary DATA_DIRECTORY first, then additional directories if configured.
    
    Args:
        json_file_path: Path to the JSON file
        
    Returns:
        Path to the corresponding PDF file or None if not found
    """
    def search_directory(directory_path, document_name, project_root=None):
        """Helper function to search for PDF in a specific directory."""
        # Handle both relative and absolute paths
        if not os.path.isabs(directory_path) and project_root:
            pdf_directory = project_root / directory_path.lstrip('./')
        else:
            pdf_directory = Path(directory_path)
        
        if not pdf_directory.exists():
            print(f"    ⚠ Directory does not exist: {pdf_directory}")
            return []
        
        print(f"    🔍 Searching in: {pdf_directory}")
        possible_paths = []
        
        # Recursive search for exact filename matches (highest priority)
        for pdf_file in pdf_directory.rglob(f"{document_name}.pdf"):
            possible_paths.append((str(pdf_file), "exact_match"))
            print(f"      [+] Found exact match: {pdf_file}")
        
        # If no exact matches, search with fuzzy matching
        if not possible_paths:
            for pdf_file in pdf_directory.rglob("*.pdf"):
                pdf_name = pdf_file.stem.lower()
                doc_name = document_name.lower()
                
                # Normalize names for comparison (handle underscores, spaces, etc.)
                pdf_normalized = pdf_name.replace('_', ' ').replace('-', ' ')
                doc_normalized = doc_name.replace('_', ' ').replace('-', ' ')
                
                match_type = None
                # Check different matching criteria in order of preference
                if pdf_normalized == doc_normalized:
                    match_type = "normalized_exact"
                elif pdf_name == doc_name:
                    match_type = "case_insensitive"
                elif doc_name in pdf_name or pdf_name in doc_name:
                    match_type = "partial_match"
                elif any(word in pdf_name for word in doc_name.split('_') if len(word) > 3):
                    match_type = "keyword_match"
                
                if match_type:
                    possible_paths.append((str(pdf_file), match_type))
                    print(f"      [+] Found {match_type}: {pdf_file}")
        
        return possible_paths

    try:
        json_path = Path(json_file_path)
        document_name = json_path.stem
        
        # Determine project root for relative path resolution
        path_parts = json_path.parts
        if 'Essentials' in path_parts:
            # Structure: project_root/Results/Essentials/document_name/recognition_json/document_name.json
            project_root = json_path.parent.parent.parent.parent.parent
        else:
            # Structure: project_root/Results/document_name/recognition_json/document_name.json  
            project_root = json_path.parent.parent.parent.parent
        
        print(f"  [SEARCH] Searching for PDF: {document_name}.pdf")
        print(f"  [PRIMARY] Searching in primary directory:")
        
        # Search in the primary directory
        all_possible_paths = search_directory(DATA_DIRECTORY, document_name, project_root)
        
        # Sort by match quality (exact matches first)
        match_priority = {
            "exact_match": 1,
            "normalized_exact": 2, 
            "case_insensitive": 3,
            "partial_match": 4,
            "keyword_match": 5
        }
        
        all_possible_paths.sort(key=lambda x: match_priority.get(x[1], 999))
        
        if all_possible_paths:
            best_match = all_possible_paths[0]
            print(f"  [SUCCESS] Best match selected ({best_match[1]}): {best_match[0]}")
            
            if len(all_possible_paths) > 1:
                print(f"  [INFO] Found {len(all_possible_paths)} total matches in directory")
            
            return best_match[0]
        else:
            print(f"  [X] No matching PDF files found in configured directory")
            print(f"    Searched directory: {DATA_DIRECTORY}")
            return None
        
    except Exception as e:
        print(f"  [ERROR] Error finding PDF file: {str(e)}")
        return None

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
                    
                    # Determine which processing method to use
                    processed_code = None
                    processing_method = "traditional"
                    
                    # Try LLM processing if enabled
                    if process_code_using_llm:
                        print(f"\n  Processing code with LLM vision (high quality mode)...")
                        try:
                            processed_code = process_code_with_llm(element, json_file_path)
                            if processed_code:
                                processing_method = "LLM"
                                print(f"  ✓ Successfully processed code with LLM!")
                                print(f"\n  LLM-Processed Code:")
                                print(f"  {'-' * 40}")
                                print(processed_code)
                                print(f"  {'-' * 40}")
                            else:
                                print(f"  ✗ LLM processing failed, falling back to traditional processing...")
                        except Exception as e:
                            print(f"  ✗ LLM processing error: {str(e)}")
                            print(f"  Falling back to traditional processing...")
                    
                    # Use traditional text-based processing if LLM failed or disabled
                    if not processed_code:
                        print(f"\n  {'Using traditional text-based code processing...' if not process_code_using_llm else 'Falling back to traditional processing...'}")
                        processed_code = clean_and_format_code(text)
                        processing_method = "traditional"
                        
                        if processed_code:
                            print(f"\n  Cleaned and Formatted Code:")
                            print(f"  {'-' * 40}")
                            print(processed_code)
                            print(f"  {'-' * 40}")
                        else:
                            print("  ✗ Failed to clean and format code")
                    
                    # Replace code in markdown if we have processed code
                    if processed_code:
                        # Search for the raw code in the markdown file
                        print(f"\n  Searching for raw code in markdown file...")
                        search_result = search_code_in_markdown(text, json_file_path)
                        
                        if search_result and search_result['found']:
                            print(f"  ✓ Found code at line {search_result['line_number']} ({search_result['match_type']} match)")
                            
                            # Replace the raw code with processed code in markdown
                            method_label = "LLM-processed" if processing_method == "LLM" else "cleaned"
                            print(f"\n  Replacing raw code with {method_label} code...")
                            success = replace_code_in_markdown(text, processed_code, json_file_path)
                            
                            if success:
                                print(f"  ✓ Raw code successfully replaced with {method_label} code!")
                            else:
                                print(f"  ✗ Failed to replace raw code with {method_label} code")
                        else:
                            print(f"  ✗ Raw code not found in markdown file - cannot replace")
                    else:
                        print("  ✗ Failed to clean and format code")
                
                # Special handling for figure elements
                elif label == "fig" and process_figures_using_llm:
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

