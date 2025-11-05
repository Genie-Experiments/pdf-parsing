"""
Script to standardize bullet points in markdown files.

This script fixes inconsistent bullet point formatting by:
1. Converting lines that start with "- •" to just "-"
2. Converting lines that start with "- ◦" to just "-"  
3. Converting lines that start with "- number." to just "number." (numbered lists)
4. Converting lines that start with just "•" to "-"
5. Converting lines that start with just "◦" to "-"
6. Preserving proper indentation levels for nested bullets
"""

import os
import re
from pathlib import Path
from utils.logger import get_logger, log_step, log_success, log_error, log_warning

def fix_bullet_points_in_text(content: str) -> tuple[str, int]:
    """
    Fix bullet point formatting in the given text content.
    
    Args:
        content (str): The markdown content to process
        
    Returns:
        tuple: (fixed_content, number_of_fixes)
    """
    lines = content.split('\n')
    fixed_lines = []
    fixes_count = 0
    
    for line in lines:
        original_line = line
        
        # Pattern 1: Lines starting with "- •" (with optional whitespace)
        # Replace with just "- " (preserving indentation)
        pattern1 = re.match(r'^(\s*)-\s*•\s*(.*)', line)
        if pattern1:
            indentation = pattern1.group(1)
            content_text = pattern1.group(2)
            line = f"{indentation}- {content_text}"
            fixes_count += 1
        else:
            # Pattern 2: Lines starting with "- ◦" (with optional whitespace)
            # Replace with just "- " (preserving indentation)
            pattern2 = re.match(r'^(\s*)-\s*◦\s*(.*)', line)
            if pattern2:
                indentation = pattern2.group(1)
                content_text = pattern2.group(2)
                line = f"{indentation}- {content_text}"
                fixes_count += 1
            else:
                # Pattern 3: Lines starting with "- number." (with optional whitespace)
                # Replace with just "number. " (preserving indentation)
                pattern3 = re.match(r'^(\s*)-\s*(\d+\.)\s*(.*)', line)
                if pattern3:
                    indentation = pattern3.group(1)
                    number = pattern3.group(2)
                    content_text = pattern3.group(3)
                    line = f"{indentation}{number} {content_text}"
                    fixes_count += 1
                else:
                    # Pattern 4: Lines starting with just "•" (with optional whitespace)
                    # Replace with "- " (preserving indentation)
                    pattern4 = re.match(r'^(\s*)•\s*(.*)', line)
                    if pattern4:
                        indentation = pattern4.group(1)
                        content_text = pattern4.group(2)
                        line = f"{indentation}- {content_text}"
                        fixes_count += 1
                    else:
                        # Pattern 5: Lines starting with just "◦" (with optional whitespace)
                        # Replace with "- " (preserving indentation)
                        pattern5 = re.match(r'^(\s*)◦\s*(.*)', line)
                        if pattern5:
                            indentation = pattern5.group(1)
                            content_text = pattern5.group(2)
                            line = f"{indentation}- {content_text}"
                            fixes_count += 1
        
        fixed_lines.append(line)
    
    return '\n'.join(fixed_lines), fixes_count

def fix_bullet_points_in_file(file_path: Path) -> bool:
    """
    Fix bullet points in a single markdown file.
    
    Args:
        file_path (Path): Path to the markdown file
        
    Returns:
        bool: True if file was processed successfully, False otherwise
    """
    logger = get_logger(__name__)
    
    try:
        # Read the file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Fix bullet points
        fixed_content, fixes_count = fix_bullet_points_in_text(content)
        
        if fixes_count > 0:
            # Write back the fixed content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(fixed_content)
            
            logger.info(f"Fixed {fixes_count} bullet points in {file_path.name}")
            return True
        else:
            logger.debug(f"No bullet point issues found in {file_path.name}")
            return True
            
    except Exception as e:
        log_error(f"Error processing {file_path}: {str(e)}")
        return False

def fix_bullet_points_batch(results_directory: str) -> None:
    """
    Fix bullet points in all markdown files in the results directory.
    
    Args:
        results_directory (str): Path to the results directory containing processed PDFs
    """
    logger = get_logger(__name__)
    
    results_path = Path(results_directory)
    
    if not results_path.exists():
        log_error(f"Results directory does not exist: {results_directory}")
        return
    
    # Find all markdown files (excluding backup files)
    markdown_files = []
    for md_file in results_path.rglob("*.md"):
        if not md_file.name.endswith("_backup.md"):
            markdown_files.append(md_file)
    
    if not markdown_files:
        log_warning(f"No markdown files found in {results_directory}")
        return
    
    logger.info(f"Found {len(markdown_files)} markdown files to process")
    
    processed_count = 0
    total_fixes = 0
    
    for md_file in markdown_files:
        logger.debug(f"Processing: {md_file.relative_to(results_path)}")
        
        # Read file to count fixes before processing
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
            _, file_fixes = fix_bullet_points_in_text(content)
            total_fixes += file_fixes
        except Exception:
            pass
        
        if fix_bullet_points_in_file(md_file):
            processed_count += 1
    
    log_success(f"Processed {processed_count}/{len(markdown_files)} files successfully")
    if total_fixes > 0:
        log_success(f"Fixed a total of {total_fixes} bullet point formatting issues")
    else:
        logger.info("No bullet point formatting issues found")