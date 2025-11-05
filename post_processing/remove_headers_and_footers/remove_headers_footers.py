import json
import re
import sys
import argparse
import os
from pathlib import Path

from utils.get_markdown_file_path import get_markdown_file_path
from utils.logger import get_logger, log_success, log_error, log_warning

# Configure logging
logger = get_logger(__name__)

def load_json_data(json_file):
    """Load and parse the JSON file"""
    try:
        with open(json_file, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        log_error(f"JSON file '{json_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        log_error(f"Error parsing JSON file: {e}")
        sys.exit(1)

def extract_headers_footers(json_data):
    """Extract header, footer, and watermark text for each page from JSON data (supports nested 'elements' list)"""
    headers_footers = {}

    # The JSON has a 'pages' key containing a list of pages
    pages = json_data.get("pages", [])

    for page_data in pages:
        if not isinstance(page_data, dict) or "page_number" not in page_data:
            continue

        page_num = page_data["page_number"]
        headers_footers[page_num] = {"headers": [], "footers": [], "watermarks": []}

        elements = page_data.get("elements", [])
        for element in elements:
            if not isinstance(element, dict):
                continue

            label = element.get("label", "").lower()
            text = element.get("text", "").strip()

            if not text:
                continue

            if "header" in label:
                headers_footers[page_num]["headers"].append(text)
            elif "foot" in label:
                headers_footers[page_num]["footers"].append(text)
            elif "watermark" in label:
                headers_footers[page_num]["watermarks"].append(text)

    return headers_footers

def get_page_content(markdown_content, page_num):
    """Extract content for a specific page from markdown"""
    if page_num == 1:
        # For page 1, get content from start to first page break
        page_break_pattern = r'<!-- page_break_1 -->'
        match = re.search(page_break_pattern, markdown_content)
        if match:
            return markdown_content[:match.start()].strip()
        else:
            # If no page break found, return entire content
            return markdown_content.strip()
    else:
        # For other pages, get content between consecutive page breaks
        start_pattern = f'<!-- page_break_{page_num - 1} -->'
        end_pattern = f'<!-- page_break_{page_num} -->'
        
        start_match = re.search(start_pattern, markdown_content)
        end_match = re.search(end_pattern, markdown_content)
        
        if start_match and end_match:
            return markdown_content[start_match.end():end_match.start()].strip()
        elif start_match and not end_match:
            # Last page case
            return markdown_content[start_match.end():].strip()
        else:
            return ""

def remove_text_from_content(content, text_to_remove):
    """Remove specific header/footer/watermark text from content, but preserve it when it's part of a Markdown heading."""
    if not text_to_remove or not content:
        return content

    # Normalize the text to remove
    normalized_text_to_remove = normalize_text_for_comparison(text_to_remove)
    
    # Process line by line and also check for paragraph matches
    lines = content.split('\n')
    updated_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Check if this line is a markdown heading that contains our text
        is_heading_with_text = (
            re.match(r'^\s*#+\s+', line) and 
            normalized_text_to_remove in normalize_text_for_comparison(line)
        )
        
        if is_heading_with_text:
            # Keep the line as-is (it's a heading)
            updated_lines.append(line)
            i += 1
        else:
            # Check for exact line match first
            normalized_line = normalize_text_for_comparison(line)
            if normalized_line == normalized_text_to_remove:
                # Skip this line (remove the exact match)
                i += 1
            else:
                # Check if this line is the start of a multi-line text that matches
                if normalized_line and normalized_text_to_remove.startswith(normalized_line):
                    # Try to match multiple consecutive lines
                    potential_match_lines = [line]
                    j = i + 1
                    combined_text = normalized_line
                    
                    while j < len(lines) and len(combined_text) < len(normalized_text_to_remove):
                        next_line = lines[j]
                        normalized_next_line = normalize_text_for_comparison(next_line)
                        if normalized_next_line:  # Skip empty lines
                            combined_text += ' ' + normalized_next_line
                            potential_match_lines.append(next_line)
                            
                            # Check if we have a complete match
                            if combined_text == normalized_text_to_remove:
                                # Found a match! Skip all these lines
                                i = j + 1
                                break
                        j += 1
                    else:
                        # No match found, keep the original line
                        updated_lines.append(line)
                        i += 1
                else:
                    # Keep all other lines unchanged
                    updated_lines.append(line)
                    i += 1
    
    # Join lines and clean up excessive blank lines
    result = '\n'.join(updated_lines)
    result = re.sub(r'\n\s*\n\s*\n+', '\n\n', result)
    
    return result.strip()


def normalize_text_for_comparison(text):
    """Normalize text for comparison by handling common character variations."""
    # Replace common character variations
    text = text.replace('\u2013', '-')  # en-dash to hyphen
    text = text.replace('\u2014', '-')  # em-dash to hyphen
    text = text.replace('\u2018', "'")  # left single quotation mark
    text = text.replace('\u2019', "'")  # right single quotation mark
    text = text.replace('\u201C', '"')  # left double quotation mark
    text = text.replace('\u201D', '"')  # right double quotation mark
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    
    return text.lower()

def update_page_content(markdown_content, page_num, updated_page_content):
    """Update the content for a specific page in the markdown"""
    if page_num == 1:
        # For page 1, replace content from start to first page break
        page_break_pattern = r'<!-- page_break_1 -->'
        match = re.search(page_break_pattern, markdown_content)
        if match:
            return updated_page_content + '\n\n' + markdown_content[match.start():]
        else:
            return updated_page_content
    else:
        # For other pages, replace content between consecutive page breaks
        start_pattern = f'<!-- page_break_{page_num - 1} -->'
        end_pattern = f'<!-- page_break_{page_num} -->'
        
        start_match = re.search(start_pattern, markdown_content)
        end_match = re.search(end_pattern, markdown_content)
        
        if start_match and end_match:
            before = markdown_content[:start_match.end()]
            after = markdown_content[end_match.start():]
            return before + '\n\n' + updated_page_content + '\n\n' + after
        elif start_match and not end_match:
            # Last page case
            before = markdown_content[:start_match.end()]
            return before + '\n\n' + updated_page_content
        else:
            return markdown_content

def remove_headers_footers(markdown_file, json_file, output_file=None):
    """Main function to remove headers and footers from markdown file"""
    
    # Create paths
    markdown_path = Path(markdown_file)
    
    # Load JSON data
    json_data = load_json_data(json_file)
    
    # Extract headers and footers information
    headers_footers = extract_headers_footers(json_data)
    
    if not headers_footers:
        log_warning("No headers or footers found in JSON data.")
        return
    
    # Read markdown content
    try:
        with open(markdown_file, 'r', encoding='utf-8') as file:
            markdown_content = file.read()
    except FileNotFoundError:
        log_error(f"Markdown file '{markdown_file}' not found.")
        sys.exit(1)
    
    # Process each page
    total_removals = 0
    updated_content = markdown_content
    
    for page_num in sorted(headers_footers.keys()):
        page_headers = headers_footers[page_num]['headers']
        page_footers = headers_footers[page_num]['footers']
        page_watermarks = headers_footers[page_num]['watermarks']

        if not page_headers and not page_footers and not page_watermarks:
            continue
        
        # Get current page content
        page_content = get_page_content(updated_content, page_num)
        
        if not page_content:
            log_warning(f"No content found for page {page_num}")
            continue
        
        original_page_content = page_content
        changes_on_page = 0
        
        if page_num == 1:
            # For page 1, keep headers but remove footers entirely
            logger.info("Processing page 1: keeping headers, removing footers")
            
            # Keep headers unchanged (do nothing with them)
            
            # Remove footers
            for footer_text in page_footers:
                new_page_content = remove_text_from_content(page_content, footer_text)
                if new_page_content != page_content:
                    page_content = new_page_content
                    changes_on_page += 1
                    logger.info(f"Removed footer from page {page_num}: '{footer_text[:50]}...'")
        else:
            # For other pages, remove headers and footers as before
            # Remove headers
            for header_text in page_headers:
                new_page_content = remove_text_from_content(page_content, header_text)
                if new_page_content != page_content:
                    page_content = new_page_content
                    changes_on_page += 1
                    logger.info(f"Removed header from page {page_num}: '{header_text[:50]}...'")
            
            # Remove footers
            for footer_text in page_footers:
                new_page_content = remove_text_from_content(page_content, footer_text)
                if new_page_content != page_content:
                    page_content = new_page_content
                    changes_on_page += 1
                    logger.info(f"Removed footer from page {page_num}: '{footer_text[:50]}...'")
        
        # Remove watermarks for all pages
        for watermark_text in page_watermarks:
            new_page_content = remove_text_from_content(page_content, watermark_text)
            if new_page_content != page_content:
                page_content = new_page_content
                changes_on_page += 1
                logger.info(f"Removed watermark from page {page_num}: '{watermark_text[:50]}...')")
        
        # Update the markdown content if changes were made
        if changes_on_page > 0:
            updated_content = update_page_content(updated_content, page_num, page_content)
            total_removals += changes_on_page
    
    # Determine output file
    if output_file is None:
        output_file = markdown_file
    
    # Write updated content
    try:
        with open(output_file, 'w', encoding='utf-8') as file:
            file.write(updated_content)
        
        log_success(f"Successfully processed '{markdown_file}'")
        logger.info(f"Total headers/footers processed: {total_removals}")
        if output_file != markdown_file:
            logger.info(f"Output written to '{output_file}'")
        else:
            logger.info("File updated in place")
            
    except Exception as e:
        log_error(f"Error writing output file: {e}")
        sys.exit(1)


def remove_headers_footers_batch(results_directory: str):
    """
    Batch process header/footer removal for all files in the results directory.
    
    Args:
        results_directory: Directory containing JSON and markdown files from processing
    """
    logger.info("Starting batch header/footer removal...")
    logger.info(f"Results directory: {results_directory}")
    logger.info("-" * 60)
    
    # Check if directory exists
    if not os.path.exists(results_directory):
        log_error(f"Results directory '{results_directory}' does not exist!")
        return False
    
    # Find all JSON files in the results directory (recursively)
    json_files = []
    for root, dirs, files in os.walk(results_directory):
        for file in files:
            if file.lower().endswith('.json') and not file.endswith('_corrections.json'):
                json_files.append(os.path.join(root, file))
    
    if not json_files:
        log_warning(f"No JSON files found in '{results_directory}'")
        return True
    
    logger.info(f"Found {len(json_files)} JSON files to process")
    
    successful_removals = 0
    failed_removals = 0
    skipped_removals = 0
    
    for i, json_path in enumerate(json_files, 1):
        try:
            # Get relative path from results directory for display
            rel_json_path = os.path.relpath(json_path, results_directory)
            logger.info(f"[{i}/{len(json_files)}] Processing: {rel_json_path}")
            
            # Use utility function to get markdown file path
            markdown_path = str(get_markdown_file_path(json_path))
            
            # Check if markdown file exists
            if not os.path.exists(markdown_path):
                log_warning(f"Skipping (markdown file not found): {markdown_path}")
                skipped_removals += 1
                continue
            
            try:
                # Load JSON data
                with open(json_path, 'r', encoding='utf-8') as file:
                    json_data = json.load(file)
                
                # Extract headers and footers information
                headers_footers = extract_headers_footers(json_data)
                
                if not headers_footers:
                    logger.info("No headers or footers found in JSON data")
                    skipped_removals += 1
                    continue
                
                # Read markdown content
                with open(markdown_path, 'r', encoding='utf-8') as file:
                    markdown_content = file.read()
                
                # Process each page
                total_removals = 0
                updated_content = markdown_content
                
                for page_num in sorted(headers_footers.keys()):
                    page_headers = headers_footers[page_num]['headers']
                    page_footers = headers_footers[page_num]['footers']
                    page_watermarks = headers_footers[page_num]['watermarks']

                    if not page_headers and not page_footers and not page_watermarks:
                        continue
                    
                    # Get current page content
                    page_content = get_page_content(updated_content, page_num)
                    
                    if not page_content:
                        continue
                    
                    original_page_content = page_content
                    changes_on_page = 0
                    
                    if page_num == 1:
                        # For page 1, keep headers but remove footers entirely
                        # Keep headers unchanged (do nothing with them)
                        
                        # Remove footers
                        for footer_text in page_footers:
                            new_page_content = remove_text_from_content(page_content, footer_text)
                            if new_page_content != page_content:
                                page_content = new_page_content
                                changes_on_page += 1
                    else:
                        # For other pages, remove headers and footers as before
                        # Remove headers
                        for header_text in page_headers:
                            new_page_content = remove_text_from_content(page_content, header_text)
                            if new_page_content != page_content:
                                page_content = new_page_content
                                changes_on_page += 1
                        
                        # Remove footers
                        for footer_text in page_footers:
                            new_page_content = remove_text_from_content(page_content, footer_text)
                            if new_page_content != page_content:
                                page_content = new_page_content
                                changes_on_page += 1
                    
                    # Remove watermarks for all pages
                    for watermark_text in page_watermarks:
                        new_page_content = remove_text_from_content(page_content, watermark_text)
                        if new_page_content != page_content:
                            page_content = new_page_content
                            changes_on_page += 1
                    
                    # Update the markdown content if changes were made
                    if changes_on_page > 0:
                        updated_content = update_page_content(updated_content, page_num, page_content)
                        total_removals += changes_on_page
                
                # Write updated content
                with open(markdown_path, 'w', encoding='utf-8') as file:
                    file.write(updated_content)
                
                successful_removals += 1
                log_success(f"Processed {total_removals} headers/footers")
                
            except Exception as e:
                failed_removals += 1
                log_error(f"Error processing files: {str(e)}")
                continue
                
        except Exception as e:
            failed_removals += 1
            log_error(f"Error processing {rel_json_path}: {str(e)}")
    
    # Print summary
    logger.info("=" * 60)
    logger.info("Header/Footer Removal Summary:")
    logger.info(f"Total JSON files found: {len(json_files)}")
    logger.info(f"Successfully processed: {successful_removals}")
    logger.info(f"Skipped files: {skipped_removals}")
    logger.info(f"Failed removals: {failed_removals}")
    
    return failed_removals == 0
