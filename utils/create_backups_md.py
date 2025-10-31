"""
Backup utility for markdown files before post-processing.

This module provides functionality to create backups of all markdown files
in a directory structure before applying post-processing steps.
"""

import os
import shutil
from utils.logger import get_logger, log_success, log_error, log_warning


def create_markdown_backup(source_dir, backup_suffix="_backup"):
    """
    Create backup copies of all markdown files in the same directory with modified filenames.
    
    Args:
        source_dir (str): Directory containing markdown files to backup
        backup_suffix (str): Suffix to add to backup filenames (default: "_backup")
    
    Returns:
        int: Number of files successfully backed up
    """
    logger = get_logger(__name__)
    
    if not os.path.exists(source_dir):
        log_warning(f"Source directory '{source_dir}' does not exist", logger)
        return 0
    
    logger.info("Creating backup of markdown files in '%s' with suffix '%s'", source_dir, backup_suffix)
    
    # Find all markdown files recursively (excluding existing backup files)
    md_files = []
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            if file.lower().endswith('.md') and not file.endswith(f'{backup_suffix}.md'):
                md_files.append(os.path.join(root, file))
    
    if not md_files:
        logger.info("No markdown files found in '%s'. Skipping backup", source_dir)
        return None
    
    logger.info("Found %d markdown files to backup", len(md_files))
    
    # Create backup files in the same directories
    try:
        copied_count = 0
        for md_file in md_files:
            # Get the directory and filename
            file_dir = os.path.dirname(md_file)
            filename = os.path.basename(md_file)
            
            # Remove .md extension and add backup suffix
            name_without_ext = os.path.splitext(filename)[0]
            backup_filename = f"{name_without_ext}{backup_suffix}.md"
            backup_file_path = os.path.join(file_dir, backup_filename)
            
            # Copy the file with new name
            shutil.copy2(md_file, backup_file_path)
            copied_count += 1
            logger.debug("Backed up: %s -> %s", filename, backup_filename)
        
        log_success(f"Successfully backed up {copied_count} markdown files with '{backup_suffix}' suffix", logger)
        return copied_count
        
    except Exception as e:
        log_error(f"Error creating backup: {e}", logger)
        return None


# Helper function to list markdown files (for testing purposes)
def list_markdown_files(directory):
    """
    List all markdown files in a directory (for verification purposes).
    
    Args:
        directory (str): Path to the directory to search
    
    Returns:
        list: List of markdown file paths
    """
    md_files = []
    if os.path.exists(directory):
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.lower().endswith('.md'):
                    md_files.append(os.path.join(root, file))
    return md_files