import argparse
import os
import re
import sys
from pathlib import Path

from utils.get_markdown_file_path import get_markdown_file_path
from utils.logger import (
    get_logger,
    log_error,
    log_file_processing,
    log_processing_stats,
    log_success,
    log_warning,
)


def replace_page_breaks(input_file, output_file=None):
    """
    Replace '---' markers with numbered markdown comments like <!-- page_break_1 -->

    Args:
        input_file (str): Path to the input markdown file
        output_file (str): Path to the output file (optional, defaults to input_file)
    """
    try:
        # Read the input file
        with open(input_file, "r", encoding="utf-8") as file:
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
        updated_content = re.sub(
            r"^---\s*$", replace_with_counter, content, flags=re.MULTILINE
        )

        # If no output file specified, overwrite the input file
        if output_file is None:
            output_file = input_file

        # Write the updated content
        with open(output_file, "w", encoding="utf-8") as file:
            file.write(updated_content)

        # Log summary
        logger = get_logger(__name__)
        total_replacements = page_break_counter - 1
        log_success(f"Successfully processed '{input_file}'", logger)
        logger.info("Replaced %d page break markers", total_replacements)
        if output_file != input_file:
            logger.info("Output written to '%s'", output_file)
        else:
            logger.info("File updated in place")

    except FileNotFoundError:
        log_error(f"File '{input_file}' not found", get_logger(__name__))
        sys.exit(1)
    except Exception as e:
        log_error(f"Error processing file: {e}", get_logger(__name__))
        sys.exit(1)


def insert_page_breaks_batch(results_directory: str):
    """
    Batch process page break insertion for all markdown files in the results directory.

    Args:
        results_directory: Directory containing JSON and markdown files from processing
    """
    logger = get_logger(__name__)

    logger.info("Starting batch page break insertion")
    logger.info("Results directory: %s", results_directory)

    # Check if directory exists
    if not os.path.exists(results_directory):
        log_error(f"Results directory '{results_directory}' does not exist!", logger)
        return False

    # Find all JSON files in the results directory (recursively)
    json_files = []
    for root, dirs, files in os.walk(results_directory):
        for file in files:
            if file.lower().endswith(".json"):
                json_files.append(os.path.join(root, file))

    if not json_files:
        logger.warning("No JSON files found in '%s'", results_directory)
        return True

    logger.info("Found %d JSON files to process", len(json_files))

    successful_insertions = 0
    failed_insertions = 0
    skipped_insertions = 0

    for i, json_path in enumerate(json_files, 1):
        try:
            # Get relative path from results directory for display
            rel_json_path = os.path.relpath(json_path, results_directory)
            logger.info("[%d/%d] Processing: %s", i, len(json_files), rel_json_path)

            # Use utility function to get markdown file path
            markdown_path = str(get_markdown_file_path(json_path))

            # Check if markdown file exists
            if not os.path.exists(markdown_path):
                log_warning(
                    f"Skipping (markdown file not found): {markdown_path}", logger
                )
                skipped_insertions += 1
                continue

            # Process the markdown file for page breaks
            try:
                # Read the markdown file
                with open(markdown_path, "r", encoding="utf-8") as file:
                    content = file.read()

                # Check if there are any '---' markers to replace
                import re

                page_break_pattern = r"^---\s*$"
                matches = re.findall(page_break_pattern, content, flags=re.MULTILINE)

                if not matches:
                    logger.debug("No page break markers found")
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
                updated_content = re.sub(
                    page_break_pattern,
                    replace_with_counter,
                    content,
                    flags=re.MULTILINE,
                )

                # Write the updated content back to the file
                with open(markdown_path, "w", encoding="utf-8") as file:
                    file.write(updated_content)

                total_replacements = page_break_counter - 1
                successful_insertions += 1
                logger.info("Replaced %d page break markers", total_replacements)

            except Exception as e:
                failed_insertions += 1
                log_error(f"Error processing markdown file: {e}", logger)
                continue

        except Exception as e:
            failed_insertions += 1
            log_error(f"Error processing {rel_json_path}: {e}", logger)

    # Log summary
    logger.info("Page Break Insertion Summary:")
    log_processing_stats(
        len(json_files), successful_insertions, failed_insertions, logger
    )
    logger.info("Skipped files: %d", skipped_insertions)

    return failed_insertions == 0
