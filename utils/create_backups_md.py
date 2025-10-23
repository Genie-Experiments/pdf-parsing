"""
Backup utility for markdown files before post-processing.

This module provides functionality to create backups of all markdown files
in a directory structure before applying post-processing steps.
"""

import os
import shutil


def create_markdown_backup(source_dir, backup_suffix="_backup"):
    """
    Create backup copies of all markdown files in the same directory with modified filenames.
    
    Args:
        source_dir (str): Path to the directory containing markdown files
        backup_suffix (str): Suffix to append to each backup filename (before .md extension)
    
    Returns:
        int: Number of files backed up, or None if error
    """
    if not os.path.exists(source_dir):
        print(f"Warning: Source directory '{source_dir}' does not exist.")
        return None
    
    print(f"Creating backup of markdown files in '{source_dir}' with suffix '{backup_suffix}'...")
    
    # Find all markdown files recursively (excluding existing backup files)
    md_files = []
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            if file.lower().endswith('.md') and not file.endswith(f'{backup_suffix}.md'):
                md_files.append(os.path.join(root, file))
    
    if not md_files:
        print(f"No markdown files found in '{source_dir}'. Skipping backup.")
        return None
    
    print(f"Found {len(md_files)} markdown files to backup.")
    
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
            print(f"  Backed up: {filename} -> {backup_filename}")
        
        print(f"Successfully backed up {copied_count} markdown files with '{backup_suffix}' suffix")
        return copied_count
        
    except Exception as e:
        print(f"Error creating backup: {str(e)}")
        return None



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




if __name__ == "__main__":
    # Example usage for testing
    test_dir = "./temp_result"  # or "./Results"
    backup_count = create_markdown_backup(test_dir)
    if backup_count:
        print(f"Backup created successfully: {backup_count} files backed up")
        
        # List all markdown files (including backups) for verification
        all_md_files = list_markdown_files(test_dir)
        backup_files = [f for f in all_md_files if '_backup.md' in f]
        print(f"Backup files created: {len(backup_files)}")
        for file in backup_files[:5]:  # Show first 5 backup files
            print(f"  - {file}")
        if len(backup_files) > 5:
            print(f"  ... and {len(backup_files) - 5} more backup files")
