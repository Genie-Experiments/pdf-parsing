import json
import re
from typing import Dict, List

from utils.logger import get_logger, log_success, log_error, log_warning

# Configure logging
logger = get_logger(__name__)


def load_json_hierarchy(json_file: str) -> Dict:
    """Load the JSON file containing section hierarchy."""
    with open(json_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_section_to_level_map(hierarchy: Dict, current_level: int = 1) -> Dict[str, int]:
    """
    Build a dictionary mapping section names to their hierarchy levels.
    
    Args:
        hierarchy: The JSON hierarchy dictionary
        current_level: Current depth level in the hierarchy
    
    Returns:
        Dictionary mapping section_name -> level
    """
    section_map = {}
    
    for section, subsections in hierarchy.items():
        section_map[section] = current_level
        
        # Recursively process subsections
        if isinstance(subsections, dict) and subsections:
            sub_map = build_section_to_level_map(subsections, current_level + 1)
            section_map.update(sub_map)
    
    return section_map


def fix_markdown_sections(markdown_file: str, json_file: str, output_file: str = None, in_place: bool = False):
    """
    Fix markdown heading levels based on JSON hierarchy with exact matching.
    
    Args:
        markdown_file: Path to input markdown file
        json_file: Path to JSON hierarchy file
        output_file: Path to output file (defaults to input_file with _fixed suffix)
        in_place: If True, modifies the original file instead of creating a new one
    """
    # Load hierarchy and build section-to-level mapping
    hierarchy = load_json_hierarchy(json_file)
    section_to_level = build_section_to_level_map(hierarchy)
    
    # Read markdown file
    with open(markdown_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    fixed_lines = []
    
    # Pattern to match markdown headings
    heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$')
    
    # Statistics
    total_headings = 0
    fixed_headings = 0
    
    for line in lines:
        match = heading_pattern.match(line.strip())
        
        if match:
            total_headings += 1
            current_hashes = match.group(1)
            heading_text = match.group(2).strip()
            
            # Check if this heading exists in our JSON hierarchy
            if heading_text in section_to_level:
                correct_level = section_to_level[heading_text]
                new_hashes = '#' * correct_level
                fixed_line = f"{new_hashes} {heading_text}\n"
                fixed_lines.append(fixed_line)
                
                fixed_headings += 1
                
                # Debug output
                if len(new_hashes) != len(current_hashes):
                    logger.info(f"Fixed: '{heading_text}' (Level {len(current_hashes)} → {correct_level})")
            else:
                # Keep original if not found in hierarchy
                fixed_lines.append(line)
                log_warning(f"No match found for: '{heading_text}' (keeping original)")
        else:
            # Not a heading, keep as is
            fixed_lines.append(line)
    
    # Determine output file path
    if in_place:
        output_path = markdown_file
    elif output_file:
        output_path = output_file
    else:
        base_name = markdown_file.rsplit('.', 1)[0]
        output_path = f"{base_name}_fixed.md"
    
    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)
    
    action = "updated in place" if in_place else f"written to: {output_path}"
    logger.info("="*60)
    log_success(f"Fixed markdown {action}")
    logger.info(f"Total sections in hierarchy: {len(section_to_level)}")
    logger.info(f"Total headings processed: {total_headings}")
    logger.info(f"Headings fixed: {fixed_headings}")
    logger.info(f"Match rate: {(fixed_headings/total_headings*100):.1f}%")
    logger.info("="*60)


def fix_markdown_headings(markdown_file: str, json_file: str, output_file: str = None):
    """
    Legacy function name for backward compatibility.
    """
    return fix_markdown_sections(markdown_file, json_file, output_file)


def batch_fix_markdown_sections(toc_json_dir: str, results_dir: str):
    """
    Batch process all markdown files and their corresponding TOC JSON files
    to fix section hierarchy in place using simple exact matching.
    
    Args:
        toc_json_dir: Directory containing TOC JSON files
        results_dir: Directory containing processed markdown files
    """
    import os
    from pathlib import Path
    
    logger.info("Starting batch processing of markdown section hierarchy (Simple Mode)...")
    logger.info(f"TOC JSON directory: {toc_json_dir}")
    logger.info(f"Results directory: {results_dir}")
    logger.info("="*80)
    
    # Find all JSON files (hierarchy files)
    toc_json_path = Path(toc_json_dir)
    json_files = list(toc_json_path.rglob("*.json"))
    
    if not json_files:
        log_warning(f"No JSON files found in {toc_json_dir}")
        return
    
    logger.info(f"Found {len(json_files)} JSON hierarchy files")
    
    # Statistics
    total_processed = 0
    total_matched = 0
    total_errors = 0
    
    # Process each TOC JSON file
    for json_file in json_files:
        try:
            # Extract the base filename (without .json extension)
            base_filename = json_file.stem
            
            logger.info("-"*60)
            logger.info(f"Processing: {json_file.name}")
            logger.info(f"Looking for markdown file: {base_filename}.md")
            
            # Find corresponding markdown file in Results directory
            results_path = Path(results_dir)
            markdown_files = list(results_path.rglob(f"{base_filename}.md"))
            
            if not markdown_files:
                log_error(f"No matching markdown file found for {base_filename}.md")
                continue
            
            if len(markdown_files) > 1:
                log_warning("Multiple markdown files found:")
                for mf in markdown_files:
                    logger.info(f"  - {mf}")
                logger.info(f"Using first match: {markdown_files[0]}")
            
            markdown_file = markdown_files[0]
            log_success(f"Found markdown file: {markdown_file}")
            
            # Process the file pair
            total_matched += 1
            logger.info("Processing file pair:")
            logger.info(f"  JSON: {json_file}")
            logger.info(f"  MD:   {markdown_file}")
            
            # Fix markdown sections in place using simple matching
            fix_markdown_sections(
                str(markdown_file), 
                str(json_file), 
                in_place=True
            )
            
            total_processed += 1
            log_success(f"Successfully processed {markdown_file.name}")
            
        except Exception as e:
            total_errors += 1
            log_error(f"Error processing {json_file.name}: {str(e)}")
    
    # Final statistics
    logger.info("="*80)
    logger.info("BATCH PROCESSING COMPLETED (Simple Mode)")
    logger.info("="*80)
    logger.info(f"Total JSON hierarchy files found: {len(json_files)}")
    logger.info(f"Matching markdown files found: {total_matched}")
    logger.info(f"Successfully processed: {total_processed}")
    logger.info(f"Errors encountered: {total_errors}")
    logger.info(f"Success rate: {(total_processed/len(json_files)*100):.1f}%")
    logger.info("="*80)
    
    return {
        'total_json_files': len(json_files),
        'total_matched': total_matched,
        'total_processed': total_processed,
        'total_errors': total_errors,
        'success_rate': total_processed/len(json_files)*100
    }