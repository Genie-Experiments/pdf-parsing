import os
import glob
from pathlib import Path
from extract_segments import extract_segments

def process_all_json_files(results_directory, segments_to_extract):
    """
    Process all JSON files in the results directory using extract_segments function
    
    Args:
        results_directory (str): Path to the results directory containing PDF processing outputs
        segments_to_extract (list): List of segment types to extract (e.g., ["tab", "code", "fig"])
    """
    
    json_files = get_json_files_list(results_directory)
    
    if not json_files:
        print(f"No JSON files found in {results_directory}")
        return
    
    print(f"Found {len(json_files)} JSON files to process")
    print(f"Extracting segments: {segments_to_extract}")
    print("=" * 60)
    
    # Process each JSON file
    for json_file in json_files:
        try:
            # Get the relative path for cleaner output
            relative_path = os.path.relpath(json_file)
            print(f"\n\n{'='*60}")
            print(f"PROCESSING: {relative_path}")
            print(f"{'='*60}")
            
            # Extract segments from this JSON file
            extract_segments(json_file, segments_to_extract)
            
        except Exception as e:
            print(f"✗ Error processing {json_file}: {str(e)}")
    
    print(f"\n\n{'='*60}")
    print("JSON processing completed!")
    print(f"{'='*60}")


def get_json_files_list(results_directory):
    """
    Get a list of all JSON files in the results directory
    
    Args:
        results_directory (str): Path to the results directory
        
    Returns:
        list: List of JSON file paths
    """
    # Convert to Path object for easier manipulation
    results_path = Path(results_directory)
    
    # Find all JSON files recursively
    json_files = list(results_path.rglob("*.json"))
    
    return [str(json_file) for json_file in json_files]
