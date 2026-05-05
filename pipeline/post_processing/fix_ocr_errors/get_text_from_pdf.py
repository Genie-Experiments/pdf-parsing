"""
Generic PDF text extraction pipeline step.

This script extracts raw text from all PDFs in the specified directory and stores
them in the output directory while maintaining the same directory structure.
"""

import os
import sys
from pathlib import Path

import fitz  # PyMuPDF

from utils.logger import get_logger, log_error, log_success, log_warning

# Configure logging
logger = get_logger(__name__)


def extract_text_with_details(pdf_path, output_file):
    """
    Extract text from a PDF file and save it to a text file.

    Args:
        pdf_path (str): Path to the PDF file
        output_file (str): Path to the output text file
    """
    try:
        doc = fitz.open(pdf_path)

        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                f.write(f"=== Page {page_num + 1} ===\n")
                f.write(f"Page Size: {page.rect.width} x {page.rect.height}\n\n")

                blocks = page.get_text("dict")["blocks"]

                for block in blocks:
                    block_type = block.get("type", -1)
                    block_number = block.get("number", "N/A")

                    if block_type == 0:  # Text block only
                        f.write(f"--- Block #{block_number} ---\n")
                        f.write(f"Type: Text\n\n")

                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                span_text = span.get("text", "")
                                if span_text.strip():  # Only write non-empty text
                                    f.write(f"    Text: {span_text}\n")

                        f.write("-" * 50 + "\n\n")

        doc.close()
        log_success(f"Extracted text from: {pdf_path}")
        return True

    except Exception as e:
        log_error(f"Error extracting text from {pdf_path}: {str(e)}")
        return False


def find_pdf_files(directory):
    """
    Recursively find all PDF files in the given directory.

    Args:
        directory (str): Directory to search for PDF files

    Returns:
        list: List of PDF file paths
    """
    pdf_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_files.append(os.path.join(root, file))
    return pdf_files


def get_output_path(pdf_path, data_dir, output_dir):
    """
    Generate the output path for a text file, creating a subfolder with the PDF name.

    Args:
        pdf_path (str): Path to the PDF file
        data_dir (str): Base data directory
        output_dir (str): Base output directory

    Returns:
        str: Output path for the text file
    """
    # Get relative path from data directory
    rel_path = os.path.relpath(pdf_path, data_dir)

    # Get the directory path and filename
    rel_dir = os.path.dirname(rel_path)
    filename = os.path.basename(pdf_path)

    # Get PDF name without extension
    pdf_name = os.path.splitext(filename)[0]

    # Create subfolder with PDF name and text file with same name
    if rel_dir:
        # If PDF is in a subdirectory, maintain that structure
        subfolder_path = os.path.join(output_dir, rel_dir, pdf_name)
    else:
        # If PDF is in root directory
        subfolder_path = os.path.join(output_dir, pdf_name)

    txt_filename = f"{pdf_name}.txt"
    output_path = os.path.join(subfolder_path, txt_filename)

    return output_path


def extract_all_pdf_texts(data_directory, raw_pdf_text_dir, force_reextract=False):
    """
    Main function to extract text from all PDFs in the specified directory
    and save them to the output directory with the same directory structure.

    Args:
        data_directory (str): Directory containing PDF files to process
        raw_pdf_text_dir (str): Directory to store extracted text files
        force_reextract (bool): If True, re-extract even if text file already exists
    """
    logger.info("Starting PDF text extraction pipeline...")
    logger.info(f"Source directory: {data_directory}")
    logger.info(f"Output directory: {raw_pdf_text_dir}")
    logger.info(f"Force re-extraction: {force_reextract}")
    logger.info("-" * 60)

    # Check if source directory exists
    if not os.path.exists(data_directory):
        log_error(f"Source directory '{data_directory}' does not exist!")
        return False

    # Create output directory if it doesn't exist
    os.makedirs(raw_pdf_text_dir, exist_ok=True)

    # Find all PDF files
    pdf_files = find_pdf_files(data_directory)

    if not pdf_files:
        log_warning(f"No PDF files found in '{data_directory}'")
        return True

    logger.info(f"Found {len(pdf_files)} PDF files to process")

    successful_extractions = 0
    failed_extractions = 0
    skipped_extractions = 0

    for i, pdf_path in enumerate(pdf_files, 1):
        logger.info(
            f"[{i}/{len(pdf_files)}] Processing: {os.path.relpath(pdf_path, data_directory)}"
        )

        # Generate output path maintaining directory structure
        output_path = get_output_path(pdf_path, data_directory, raw_pdf_text_dir)

        # Skip if output file already exists (unless force_reextract is True)
        if os.path.exists(output_path) and not force_reextract:
            log_warning(
                f"Skipping (text file already exists): {os.path.relpath(output_path, raw_pdf_text_dir)}"
            )
            skipped_extractions += 1
            continue

        # Extract text
        if extract_text_with_details(pdf_path, output_path):
            successful_extractions += 1
            log_success(f"Saved to: {os.path.relpath(output_path, raw_pdf_text_dir)}")
        else:
            failed_extractions += 1

    # Print summary
    logger.info("=" * 60)
    logger.info("PDF Text Extraction Summary:")
    logger.info(f"Total PDFs found: {len(pdf_files)}")
    logger.info(f"Successful extractions: {successful_extractions}")
    logger.info(f"Skipped extractions: {skipped_extractions}")
    logger.info(f"Failed extractions: {failed_extractions}")
    logger.info(f"Output directory: {raw_pdf_text_dir}")

    return failed_extractions == 0
