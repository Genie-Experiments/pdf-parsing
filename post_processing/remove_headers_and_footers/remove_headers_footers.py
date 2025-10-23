import json
import re
import sys
import argparse
import os
from pathlib import Path

# Add utils directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'utils'))
from get_markdown_file_path import get_markdown_file_path



def load_json_data(json_file):
    """Load and parse the JSON file"""
    try:
        with open(json_file, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Error: JSON file '{json_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file: {e}")
        sys.exit(1)

def extract_headers_footers(json_data):
    """Extract header and footer text for each page from JSON data (supports nested 'elements' list)"""
    headers_footers = {}

    # The JSON has a 'pages' key containing a list of pages
    pages = json_data.get("pages", [])

    for page_data in pages:
        if not isinstance(page_data, dict) or "page_number" not in page_data:
            continue

        page_num = page_data["page_number"]
        headers_footers[page_num] = {"headers": [], "footers": []}

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
    """Remove specific header/footer text from content, but preserve it when it's part of a Markdown heading."""
    if not text_to_remove or not content:
        return content

    # Process line by line for exact matching
    lines = content.split('\n')
    updated_lines = []
    
    for line in lines:
        # Check if this line is a markdown heading that contains our text
        is_heading_with_text = (
            re.match(r'^\s*#+\s+', line) and 
            text_to_remove.lower() in line.lower()
        )
        
        if is_heading_with_text:
            # Keep the line as-is (it's a heading)
            updated_lines.append(line)
        else:
            # Check if this line contains EXACTLY the header/footer text (case-insensitive)
            if line.strip().lower() == text_to_remove.lower():
                # Skip this line (remove the exact match)
                continue
            else:
                # Keep all other lines unchanged
                updated_lines.append(line)
    
    # Join lines and clean up excessive blank lines
    result = '\n'.join(updated_lines)
    result = re.sub(r'\n\s*\n\s*\n+', '\n\n', result)
    
    return result.strip()


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
        print("No headers or footers found in JSON data.")
        return
    
    # Read markdown content
    try:
        with open(markdown_file, 'r', encoding='utf-8') as file:
            markdown_content = file.read()
    except FileNotFoundError:
        print(f"Error: Markdown file '{markdown_file}' not found.")
        sys.exit(1)
    
    # Process each page
    total_removals = 0
    updated_content = markdown_content
    
    for page_num in sorted(headers_footers.keys()):
        # Skip header/footer removal for the first page
        if page_num == 1:
            print("Skipping header/footer removal for page 1")
            continue

        page_headers = headers_footers[page_num]['headers']
        page_footers = headers_footers[page_num]['footers']

        if not page_headers and not page_footers:
            continue
        
        # Get current page content
        page_content = get_page_content(updated_content, page_num)
        
        if not page_content:
            print(f"Warning: No content found for page {page_num}")
            continue
        
        original_page_content = page_content
        removals_on_page = 0
        
        # Remove headers
        for header_text in page_headers:
            if header_text in page_content:
                page_content = remove_text_from_content(page_content, header_text)
                removals_on_page += 1
                print(f"Removed header from page {page_num}: '{header_text[:50]}...'")
        
        # Remove footers
        for footer_text in page_footers:
            if footer_text in page_content:
                page_content = remove_text_from_content(page_content, footer_text)
                removals_on_page += 1
                print(f"Removed footer from page {page_num}: '{footer_text[:50]}...'")
        
        # Update the markdown content if changes were made
        if removals_on_page > 0:
            updated_content = update_page_content(updated_content, page_num, page_content)
            total_removals += removals_on_page
    
    # Determine output file
    if output_file is None:
        output_file = markdown_file
    
    # Write updated content
    try:
        with open(output_file, 'w', encoding='utf-8') as file:
            file.write(updated_content)
        
        print(f"\nSuccessfully processed '{markdown_file}'")
        print(f"Total headers/footers removed: {total_removals}")
        if output_file != markdown_file:
            print(f"Output written to '{output_file}'")
        else:
            print(f"File updated in place")
            
    except Exception as e:
        print(f"Error writing output file: {e}")
        sys.exit(1)


def remove_headers_footers_batch(results_directory: str):
    """
    Batch process header/footer removal for all files in the results directory.
    
    Args:
        results_directory: Directory containing JSON and markdown files from processing
    """
    print("Starting batch header/footer removal...")
    print(f"Results directory: {results_directory}")
    print("-" * 60)
    
    # Check if directory exists
    if not os.path.exists(results_directory):
        print(f"Error: Results directory '{results_directory}' does not exist!")
        return False
    
    # Find all JSON files in the results directory (recursively)
    json_files = []
    for root, dirs, files in os.walk(results_directory):
        for file in files:
            if file.lower().endswith('.json') and not file.endswith('_corrections.json'):
                json_files.append(os.path.join(root, file))
    
    if not json_files:
        print(f"No JSON files found in '{results_directory}'")
        return True
    
    print(f"Found {len(json_files)} JSON files to process\n")
    
    successful_removals = 0
    failed_removals = 0
    skipped_removals = 0
    
    for i, json_path in enumerate(json_files, 1):
        try:
            # Get relative path from results directory for display
            rel_json_path = os.path.relpath(json_path, results_directory)
            print(f"[{i}/{len(json_files)}] Processing: {rel_json_path}")
            
            # Use utility function to get markdown file path
            markdown_path = str(get_markdown_file_path(json_path))
            
            # Check if markdown file exists
            if not os.path.exists(markdown_path):
                print(f"  → Skipping (markdown file not found): {markdown_path}")
                skipped_removals += 1
                continue
            
            try:
                # Load JSON data
                with open(json_path, 'r', encoding='utf-8') as file:
                    json_data = json.load(file)
                
                # Extract headers and footers information
                headers_footers = extract_headers_footers(json_data)
                
                if not headers_footers:
                    print(f"  → No headers or footers found in JSON data")
                    skipped_removals += 1
                    continue
                
                # Read markdown content
                with open(markdown_path, 'r', encoding='utf-8') as file:
                    markdown_content = file.read()
                
                # Process each page
                total_removals = 0
                updated_content = markdown_content
                
                for page_num in sorted(headers_footers.keys()):
                    # Skip header/footer removal for the first page
                    if page_num == 1:
                        continue

                    page_headers = headers_footers[page_num]['headers']
                    page_footers = headers_footers[page_num]['footers']

                    if not page_headers and not page_footers:
                        continue
                    
                    # Get current page content
                    page_content = get_page_content(updated_content, page_num)
                    
                    if not page_content:
                        continue
                    
                    original_page_content = page_content
                    removals_on_page = 0
                    
                    # Remove headers
                    for header_text in page_headers:
                        if header_text in page_content:
                            page_content = remove_text_from_content(page_content, header_text)
                            removals_on_page += 1
                    
                    # Remove footers
                    for footer_text in page_footers:
                        if footer_text in page_content:
                            page_content = remove_text_from_content(page_content, footer_text)
                            removals_on_page += 1
                    
                    # Update the markdown content if changes were made
                    if removals_on_page > 0:
                        updated_content = update_page_content(updated_content, page_num, page_content)
                        total_removals += removals_on_page
                
                # Write updated content
                with open(markdown_path, 'w', encoding='utf-8') as file:
                    file.write(updated_content)
                
                successful_removals += 1
                print(f"  → Removed {total_removals} headers/footers")
                
            except Exception as e:
                failed_removals += 1
                print(f"  → Error processing files: {str(e)}")
                continue
                
        except Exception as e:
            failed_removals += 1
            print(f"  → Error processing {rel_json_path}: {str(e)}")
        
        print()  # Empty line for readability
    
    # Print summary
    print("=" * 60)
    print("Header/Footer Removal Summary:")
    print(f"Total JSON files found: {len(json_files)}")
    print(f"Successfully processed: {successful_removals}")
    print(f"Skipped files: {skipped_removals}")
    print(f"Failed removals: {failed_removals}")
    
    return failed_removals == 0


def main():
    parser = argparse.ArgumentParser(
        description="Remove PDF page headers and footers from markdown file using JSON data"
    )
    parser.add_argument(
        'markdown_file', 
        help='Path to the input markdown file'
    )
    parser.add_argument(
        'json_file', 
        help='Path to the JSON file containing page structure data'
    )
    parser.add_argument(
        '-o', '--output', 
        help='Path to the output file (optional, defaults to input file)'
    )
    
    args = parser.parse_args()
    
    remove_headers_footers(args.markdown_file, args.json_file, args.output)


if __name__ == "__main__":
    # Check if running with command line arguments or as batch processor
    if len(sys.argv) == 1:
        # No arguments provided - run as batch processor with config
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))
        from config import OUTPUT_DIRECTORY
        
        success = remove_headers_footers_batch(OUTPUT_DIRECTORY)
        
        if success:
            print("\n✅ Header/footer removal completed successfully!")
        else:
            print("\n❌ Header/footer removal failed!")
        
        sys.exit(0 if success else 1)
    else:
        # Command line arguments provided - run original functionality
        main()