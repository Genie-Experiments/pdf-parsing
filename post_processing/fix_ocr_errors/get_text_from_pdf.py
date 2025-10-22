"""
Generic PDF text extraction pipeline step.

This script extracts raw text from all PDFs in the specified directory and stores
them in the output directory while maintaining the same directory structure.
"""

import fitz  # PyMuPDF
import os
import sys
from pathlib import Path


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

        with open(output_file, 'w', encoding='utf-8') as f:
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
                                span_text = span.get('text', '')
                                if span_text.strip():  # Only write non-empty text
                                    f.write(f"    Text: {span_text}\n")

                        f.write("-" * 50 + "\n\n")
        
        doc.close()
        print(f"✓ Extracted text from: {pdf_path}")
        return True
        
    except Exception as e:
        print(f"✗ Error extracting text from {pdf_path}: {str(e)}")
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
            if file.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, file))
    return pdf_files


def get_output_path(pdf_path, data_dir, output_dir):
    """
    Generate the output path for a text file, maintaining directory structure.
    
    Args:
        pdf_path (str): Path to the PDF file
        data_dir (str): Base data directory
        output_dir (str): Base output directory
        
    Returns:
        str: Output path for the text file
    """
    # Get relative path from data directory
    rel_path = os.path.relpath(pdf_path, data_dir)
    
    # Change extension from .pdf to .txt
    base_name = os.path.splitext(rel_path)[0]
    txt_filename = f"{base_name}.txt"
    
    # Create full output path
    output_path = os.path.join(output_dir, txt_filename)
    
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
    print("Starting PDF text extraction pipeline...")
    print(f"Source directory: {data_directory}")
    print(f"Output directory: {raw_pdf_text_dir}")
    print(f"Force re-extraction: {force_reextract}")
    print("-" * 60)
    
    # Check if source directory exists
    if not os.path.exists(data_directory):
        print(f"Error: Source directory '{data_directory}' does not exist!")
        return False
    
    # Create output directory if it doesn't exist
    os.makedirs(raw_pdf_text_dir, exist_ok=True)
    
    # Find all PDF files
    pdf_files = find_pdf_files(data_directory)
    
    if not pdf_files:
        print(f"No PDF files found in '{data_directory}'")
        return True
    
    print(f"Found {len(pdf_files)} PDF files to process\n")
    
    successful_extractions = 0
    failed_extractions = 0
    skipped_extractions = 0
    
    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"[{i}/{len(pdf_files)}] Processing: {os.path.relpath(pdf_path, data_directory)}")
        
        # Generate output path maintaining directory structure
        output_path = get_output_path(pdf_path, data_directory, raw_pdf_text_dir)
        
        # Skip if output file already exists (unless force_reextract is True)
        if os.path.exists(output_path) and not force_reextract:
            print(f"  → Skipping (text file already exists): {os.path.relpath(output_path, raw_pdf_text_dir)}")
            skipped_extractions += 1
            continue
        
        # Extract text
        if extract_text_with_details(pdf_path, output_path):
            successful_extractions += 1
            print(f"  → Saved to: {os.path.relpath(output_path, raw_pdf_text_dir)}")
        else:
            failed_extractions += 1
        
        print()  # Empty line for readability
    
    # Print summary
    print("=" * 60)
    print("PDF Text Extraction Summary:")
    print(f"Total PDFs found: {len(pdf_files)}")
    print(f"Successful extractions: {successful_extractions}")
    print(f"Skipped extractions: {skipped_extractions}")
    print(f"Failed extractions: {failed_extractions}")
    print(f"Output directory: {raw_pdf_text_dir}")
    
    return failed_extractions == 0
