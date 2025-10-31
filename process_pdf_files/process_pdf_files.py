import os
import glob
import subprocess
from pathlib import Path
import sys

from utils.logger import get_logger, log_success, log_error, log_warning

# Configure logging
logger = get_logger(__name__)

def process_pdf_files(data_dir, results_dir, dolphin_script, model_path):
    """
    Process all PDF files recursively in the data directory using Dolphin model.
    Maintains the same directory structure in the results directory.
    
    Args:
        data_dir (str): Root directory to search for PDF files
        results_dir (str): Root directory where results will be saved
        dolphin_script (str): Path to the Dolphin processing script
        model_path (str): Path to the Dolphin model
    """
    
    # Convert to Path objects for easier manipulation
    data_path = Path(data_dir)
    results_path = Path(results_dir)
    
    # Ensure results directory exists
    results_path.mkdir(parents=True, exist_ok=True)
    
    # Find all PDF files recursively
    pdf_files = list(data_path.rglob("*.pdf"))
    
    if not pdf_files:
        log_warning(f"No PDF files found in {data_dir}")
        return
    
    logger.info(f"Found {len(pdf_files)} PDF files to process")
    
    # Process each PDF file
    for pdf_file in pdf_files:
        try:
            # Get PDF filename without extension
            pdf_name = pdf_file.stem
            
            # Calculate relative path from data_dir to maintain directory structure
            relative_path = pdf_file.relative_to(data_path)
            relative_dir = relative_path.parent
            
            logger.info(f"Processing: {relative_path}")
            
            # Create output directory maintaining the same structure
            # Structure: results_dir/relative_dir/pdf_name/
            output_dir = results_path / relative_dir / pdf_name
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Run the inference command on each PDF file and save the output in the respective directory
            cmd = [
                sys.executable, 
                dolphin_script,
                "--model_path", model_path,
                "--input_path", str(pdf_file),
                "--save_dir", str(output_dir)
            ]
            
            logger.info(f"Running command: {' '.join(cmd)}")
            logger.info(f"Output directory: {output_dir}")
            
            # Execute the command
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
            
            if result.returncode == 0:
                log_success(f"Successfully processed {pdf_name}")
                if result.stdout:
                    logger.info(f"Output: {result.stdout}")
            else:
                log_error(f"Error processing {pdf_name}")
                logger.info(f"Error: {result.stderr}")
                
        except Exception as e:
            log_error(f"Exception while processing {pdf_file}: {str(e)}")
    
    log_success("PDF processing pipeline completed!")
