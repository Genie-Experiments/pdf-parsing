from config.config import DATA_DIRECTORY
from pathlib import Path
import os
from utils.logger import get_logger, log_success, log_error

def get_pdf_file_path(json_file_path):
    """
    Find the corresponding PDF file in the configured data directory.
    
    Args:
        json_file_path: Path to the JSON file
        
    Returns:
        Path to the corresponding PDF file or None if not found
    """
    try:
        json_path = Path(json_file_path)
        document_name = json_path.stem
        
        # Resolve data directory path
        if os.path.isabs(DATA_DIRECTORY):
            data_dir = Path(DATA_DIRECTORY)
        else:
            data_dir = Path.cwd() / DATA_DIRECTORY.lstrip('./')
        
        logger = get_logger(__name__)
        
        if not data_dir.exists():
            log_error(f"Data directory not found: {data_dir}", logger)
            return None
        
        logger.debug("Searching for PDF: %s.pdf", document_name)
        
        # Search for exact match first
        for pdf_file in data_dir.rglob(f"{document_name}.pdf"):
            log_success(f"PDF found: {pdf_file}", logger)
            return str(pdf_file)
        
        logger.warning("PDF not found in: %s", data_dir)
        return None
        
    except Exception as e:
        log_error(f"Error finding PDF file: {e}", logger)
        return None
