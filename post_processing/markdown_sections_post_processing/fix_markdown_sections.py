import json
import re
from typing import Dict, List, Tuple, Optional
from difflib import SequenceMatcher


def load_json_hierarchy(json_file: str) -> Dict:
    """Load the JSON file containing section hierarchy."""
    with open(json_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_section_hierarchy(hierarchy: Dict, current_level: int = 1, 
                           parent_path: List[str] = None) -> List[Tuple[str, int, List[str]]]:
    """
    Build a list of (section_name, level, path) tuples from hierarchy.
    
    Args:
        hierarchy: The JSON hierarchy dictionary
        current_level: Current depth level in the hierarchy
        parent_path: List of parent section names
    
    Returns:
        List of tuples: (section_name, level, full_path)
    """
    if parent_path is None:
        parent_path = []
    
    sections = []
    
    for section, subsections in hierarchy.items():
        current_path = parent_path + [section]
        sections.append((section, current_level, current_path))
        
        # Recursively process subsections
        if isinstance(subsections, dict) and subsections:
            sub_sections = build_section_hierarchy(subsections, current_level + 1, current_path)
            sections.extend(sub_sections)
    
    return sections


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    # Remove extra whitespace
    text = ' '.join(text.split())
    # Convert to lowercase for comparison
    text = text.lower()
    # Remove common punctuation
    text = re.sub(r'[^\w\s-]', '', text)
    return text.strip()


def calculate_similarity(str1: str, str2: str) -> float:
    """Calculate similarity ratio between two strings."""
    return SequenceMatcher(None, normalize_text(str1), normalize_text(str2)).ratio()


def find_best_match_with_context(heading_text: str, 
                                 sections: List[Tuple[str, int, List[str]]],
                                 current_context: List[str],
                                 used_sections: set) -> Tuple[Optional[str], Optional[int], Optional[List[str]]]:
    """
    Find the best matching section with context awareness.
    
    Args:
        heading_text: The heading text from markdown
        sections: List of (section_name, level, path) tuples
        current_context: Current section context (parent sections)
        used_sections: Set of already matched section paths
    
    Returns:
        Tuple of (section_name, level, path) or (None, None, None) if no match
    """
    normalized_heading = normalize_text(heading_text)
    best_match = None
    best_score = 0.0
    
    for section_name, level, path in sections:
        # Skip already used sections
        path_key = '/'.join(path)
        if path_key in used_sections:
            continue
        
        normalized_section = normalize_text(section_name)
        
        # Calculate base similarity
        similarity = calculate_similarity(heading_text, section_name)
        
        # Boost score if section is a child of current context
        context_boost = 0.0
        if current_context and len(path) > len(current_context):
            # Check if this section is under the current context
            if path[:len(current_context)] == current_context:
                context_boost = 0.3
        
        # Boost score for exact normalized match
        exact_boost = 0.0
        if normalized_heading == normalized_section:
            exact_boost = 0.5
        
        # Boost score if one contains the other
        containment_boost = 0.0
        if normalized_section in normalized_heading or normalized_heading in normalized_section:
            containment_boost = 0.2
        
        # Penalty for being too far off in expected hierarchy
        level_penalty = 0.0
        if current_context:
            expected_level = len(current_context) + 1
            if abs(level - expected_level) > 2:
                level_penalty = 0.1
        
        total_score = similarity + context_boost + exact_boost + containment_boost - level_penalty
        
        if total_score > best_score and similarity > 0.5:  # Minimum 50% similarity
            best_score = total_score
            best_match = (section_name, level, path)
    
    return best_match if best_match else (None, None, None)


def update_context(context: List[str], new_section: str, new_level: int, 
                   all_sections: List[Tuple[str, int, List[str]]]) -> List[str]:
    """
    Update the current context based on the new section and level.
    
    Args:
        context: Current context (list of parent section names)
        new_section: The new section that was matched
        new_level: Level of the new section
        all_sections: All sections for reference
    
    Returns:
        Updated context list
    """
    # Find the full path of the new section
    for section_name, level, path in all_sections:
        if section_name == new_section and level == new_level:
            # Return the path excluding the current section
            return path[:-1]
    
    # Fallback: adjust context based on level
    if new_level <= len(context):
        return context[:new_level - 1]
    else:
        return context + [new_section]


def fix_markdown_sections(markdown_file: str, json_file: str, output_file: str = None, in_place: bool = False):
    """
    Fix markdown heading levels based on JSON hierarchy with intelligent matching.
    
    Args:
        markdown_file: Path to input markdown file
        json_file: Path to JSON hierarchy file
        output_file: Path to output file (defaults to input_file with _fixed suffix)
        in_place: If True, modifies the original file instead of creating a new one
    """
    # Load hierarchy and build section list
    hierarchy = load_json_hierarchy(json_file)
    sections = build_section_hierarchy(hierarchy)
    
    # Read markdown file
    with open(markdown_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Track context and used sections
    current_context = []
    used_sections = set()
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
            
            # Find matching section with context awareness
            matched_section, correct_level, matched_path = find_best_match_with_context(
                heading_text, sections, current_context, used_sections
            )
            
            if matched_section and correct_level:
                # Use the section name from JSON (prioritize JSON naming)
                corrected_heading = matched_section
                
                # Create correct heading with proper level
                new_hashes = '#' * correct_level
                fixed_line = f"{new_hashes} {corrected_heading}\n"
                fixed_lines.append(fixed_line)
                
                # Mark this section as used
                if matched_path:
                    used_sections.add('/'.join(matched_path))
                    # Update context to the parent path of the matched section
                    current_context = matched_path[:-1]
                
                fixed_headings += 1
                
                # Debug output
                if corrected_heading != heading_text or len(new_hashes) != len(current_hashes):
                    print(f"Fixed: '{heading_text}' → '{corrected_heading}' (Level {len(current_hashes)} → {correct_level})")
            else:
                # Keep original if no match found
                fixed_lines.append(line)
                print(f"No match found for: '{heading_text}' (keeping original)")
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
    print(f"\n{'='*60}")
    print(f"Fixed markdown {action}")
    print(f"Total sections in hierarchy: {len(sections)}")
    print(f"Total headings processed: {total_headings}")
    print(f"Headings fixed: {fixed_headings}")
    print(f"Match rate: {(fixed_headings/total_headings*100):.1f}%")
    print(f"{'='*60}")


def fix_markdown_headings(markdown_file: str, json_file: str, output_file: str = None):
    """
    Legacy function name for backward compatibility.
    """
    return fix_markdown_sections(markdown_file, json_file, output_file)


def batch_fix_markdown_sections(toc_json_dir: str, results_dir: str):
    """
    Batch process all markdown files and their corresponding TOC JSON files
    to fix section hierarchy in place.
    
    Args:
        toc_json_dir: Directory containing TOC JSON files
        results_dir: Directory containing processed markdown files
    """
    import os
    from pathlib import Path
    
    print(f"Starting batch processing of markdown section hierarchy...")
    print(f"TOC JSON directory: {toc_json_dir}")
    print(f"Results directory: {results_dir}")
    print(f"{'='*80}")
    
    # Find all JSON files (hierarchy files)
    toc_json_path = Path(toc_json_dir)
    json_files = list(toc_json_path.rglob("*.json"))
    
    if not json_files:
        print(f"No JSON files found in {toc_json_dir}")
        return
    
    print(f"Found {len(json_files)} JSON hierarchy files")
    
    # Statistics
    total_processed = 0
    total_matched = 0
    total_errors = 0
    
    # Process each TOC JSON file
    for json_file in json_files:
        try:
            # Extract the base filename (without .json extension)
            base_filename = json_file.stem
            
            print(f"\n{'-'*60}")
            print(f"Processing: {json_file.name}")
            print(f"Looking for markdown file: {base_filename}.md")
            
            # Find corresponding markdown file in Results directory
            results_path = Path(results_dir)
            markdown_files = list(results_path.rglob(f"{base_filename}.md"))
            
            if not markdown_files:
                print(f"  ✗ No matching markdown file found for {base_filename}.md")
                continue
            
            if len(markdown_files) > 1:
                print(f"  ! Multiple markdown files found:")
                for mf in markdown_files:
                    print(f"    - {mf}")
                print(f"  Using first match: {markdown_files[0]}")
            
            markdown_file = markdown_files[0]
            print(f"  ✓ Found markdown file: {markdown_file}")
            
            # Process the file pair
            total_matched += 1
            print(f"\n  Processing file pair:")
            print(f"    JSON: {json_file}")
            print(f"    MD:   {markdown_file}")
            
            # Fix markdown sections in place
            fix_markdown_sections(
                str(markdown_file), 
                str(json_file), 
                in_place=True
            )
            
            total_processed += 1
            print(f"  ✓ Successfully processed {markdown_file.name}")
            
        except Exception as e:
            total_errors += 1
            print(f"  ✗ Error processing {json_file.name}: {str(e)}")
    
    # Final statistics
    print(f"\n{'='*80}")
    print(f"BATCH PROCESSING COMPLETED")
    print(f"{'='*80}")
    print(f"Total JSON hierarchy files found: {len(json_files)}")
    print(f"Matching markdown files found: {total_matched}")
    print(f"Successfully processed: {total_processed}")
    print(f"Errors encountered: {total_errors}")
    print(f"Success rate: {(total_processed/len(json_files)*100):.1f}%")
    print(f"{'='*80}")
    
    return {
        'total_json_files': len(json_files),
        'total_matched': total_matched,
        'total_processed': total_processed,
        'total_errors': total_errors,
        'success_rate': total_processed/len(json_files)*100
    }