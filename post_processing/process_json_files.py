import glob
import os
from pathlib import Path

from post_processing.refine_segments import refine_segments
from utils.logger import (
    get_logger,
    log_error,
    log_file_processing,
    log_processing_stats,
)


def process_all_json_files(
    results_directory,
    segments_to_extract,
    process_code_using_llm=False,
    process_figures_using_llm=False,
):
    """
    Process all JSON files in the results directory using extract_segments function

    Args:
        results_directory (str): Path to the results directory containing PDF processing outputs
        segments_to_extract (list): List of segment types to extract (e.g., ["tab", "code", "fig"])
    """
    logger = get_logger(__name__)

    json_files = get_json_files_list(results_directory)

    if not json_files:
        logger.warning("No JSON files found in %s", results_directory)
        return

    logger.info("Found %d JSON files to process", len(json_files))
    logger.info("Extracting segments: %s", segments_to_extract)

    processed = 0
    failed = 0

    # Process each JSON file
    for json_file in json_files:
        try:
            log_file_processing(json_file, logger)

            # Extract segments from this JSON file
            refine_segments(
                json_file,
                segments_to_extract,
                process_code_using_llm,
                process_figures_using_llm,
            )
            processed += 1

        except Exception as e:
            log_error(f"Error processing {json_file}: {e}", logger)
            failed += 1

    log_processing_stats(len(json_files), processed, failed, logger)


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
