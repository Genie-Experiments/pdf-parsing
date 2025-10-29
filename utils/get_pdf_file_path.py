from config.config import DATA_DIRECTORY
from pathlib import Path
import os

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
        
        if not data_dir.exists():
            print(f"  ✗ Data directory not found: {data_dir}")
            return None
        
        print(f"  Searching for PDF: {document_name}.pdf")
        
        # Search for exact match first
        for pdf_file in data_dir.rglob(f"{document_name}.pdf"):
            print(f"  ✓ PDF found: {pdf_file}")
            return str(pdf_file)
        
        print(f"  ✗ PDF not found in: {data_dir}")
        return None
        
    except Exception as e:
        print(f"  ✗ Error finding PDF file: {str(e)}")
        return None
