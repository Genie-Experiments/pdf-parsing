import re
import sys
import argparse
import os
from pathlib import Path

# Add utils directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'utils'))
from get_markdown_file_path import get_markdown_file_path

def replace_page_breaks(input_file, output_file=None):
    """
    Replace '---' markers with numbered markdown comments like <!-- page_break_1 -->
    
    Args:
        input_file (str): Path to the input markdown file
        output_file (str): Path to the output file (optional, defaults to input_file)
    """
    try:
        # Read the input file
        with open(input_file, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Counter for page breaks
        page_break_counter = 1
        
        # Function to replace each occurrence with numbered comment
        def replace_with_counter(match):
            nonlocal page_break_counter
            replacement = f"<!-- page_break_{page_break_counter} -->"
            page_break_counter += 1
            return replacement
        
        # Replace all occurrences of '---' with numbered page break comments
        # Updated pattern to handle trailing whitespace
        updated_content = re.sub(r'^---\s*$', replace_with_counter, content, flags=re.MULTILINE)
        
        # If no output file specified, overwrite the input file
        if output_file is None:
            output_file = input_file
        
        # Write the updated content
        with open(output_file, 'w', encoding='utf-8') as file:
            file.write(updated_content)
        
        # Print summary
        total_replacements = page_break_counter - 1
        print(f"Successfully processed '{input_file}'")
        print(f"Replaced {total_replacements} page break markers")
        if output_file != input_file:
            print(f"Output written to '{output_file}'")
        else:
            print(f"File updated in place")
            
    except FileNotFoundError:
        print(f"Error: File '{input_file}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error processing file: {e}")
        sys.exit(1)


def insert_page_breaks_batch(results_directory: str):
    """
    Batch process page break insertion for all markdown files in the results directory.
    
    Args:
        results_directory: Directory containing JSON and markdown files from processing
    """
    print("Starting batch page break insertion...")
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
            if file.lower().endswith('.json'):
                json_files.append(os.path.join(root, file))
    
    if not json_files:
        print(f"No JSON files found in '{results_directory}'")
        return True
    
    print(f"Found {len(json_files)} JSON files to process\n")
    
    successful_insertions = 0
    failed_insertions = 0
    skipped_insertions = 0
    
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
                skipped_insertions += 1
                continue
            
            # Process the markdown file for page breaks
            try:
                # Read the markdown file
                with open(markdown_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                
                # Check if there are any '---' markers to replace
                import re
                page_break_pattern = r'^---\s*$'
                matches = re.findall(page_break_pattern, content, flags=re.MULTILINE)
                
                if not matches:
                    print(f"  → No page break markers found")
                    skipped_insertions += 1
                    continue
                
                # Counter for page breaks
                page_break_counter = 1
                
                # Function to replace each occurrence with numbered comment
                def replace_with_counter(match):
                    nonlocal page_break_counter
                    replacement = f"<!-- page_break_{page_break_counter} -->"
                    page_break_counter += 1
                    return replacement
                
                # Replace all occurrences of '---' with numbered page break comments
                updated_content = re.sub(page_break_pattern, replace_with_counter, content, flags=re.MULTILINE)
                
                # Write the updated content back to the file
                with open(markdown_path, 'w', encoding='utf-8') as file:
                    file.write(updated_content)
                
                total_replacements = page_break_counter - 1
                successful_insertions += 1
                print(f"  → Replaced {total_replacements} page break markers")
                
            except Exception as e:
                failed_insertions += 1
                print(f"  → Error processing markdown file: {str(e)}")
                continue
                
        except Exception as e:
            failed_insertions += 1
            print(f"  → Error processing {rel_json_path}: {str(e)}")
        
        print()  # Empty line for readability
    
    # Print summary
    print("=" * 60)
    print("Page Break Insertion Summary:")
    print(f"Total JSON files found: {len(json_files)}")
    print(f"Successfully processed: {successful_insertions}")
    print(f"Skipped files: {skipped_insertions}")
    print(f"Failed insertions: {failed_insertions}")
    
    return failed_insertions == 0


def main():
    parser = argparse.ArgumentParser(
        description="Replace '---' page break markers with numbered markdown comments"
    )
    parser.add_argument(
        'input_file', 
        help='Path to the input markdown file'
    )
    parser.add_argument(
        '-o', '--output', 
        help='Path to the output file (optional, defaults to input file)'
    )
    
    args = parser.parse_args()
    
    replace_page_breaks(args.input_file, args.output)


if __name__ == "__main__":
    # Check if running with command line arguments or as batch processor
    if len(sys.argv) == 1:
        # No arguments provided - run as batch processor with config
        import sys
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))
        from config import OUTPUT_DIRECTORY
        
        success = insert_page_breaks_batch(OUTPUT_DIRECTORY)
        
        if success:
            print("\n✅ Page break insertion completed successfully!")
        else:
            print("\n❌ Page break insertion failed!")
        
        sys.exit(0 if success else 1)
    else:
        # Command line arguments provided - run original functionality
        main()

