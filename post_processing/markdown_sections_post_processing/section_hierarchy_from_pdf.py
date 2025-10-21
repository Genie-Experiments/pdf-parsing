import pymupdf  # PyMuPDF
import json
import re
import os
import sys
from collections import defaultdict
from pathlib import Path

# Add config directory to path to import config
sys.path.append(os.path.join(os.path.dirname(__file__), 'config'))
from config.config import DATA_DIRECTORY


def extract_heading_candidates_from_pdf(pdf_path):
    """
    Extract all potential headings from PDF with their styling properties.

    Args:
        pdf_path: Path to PDF file

    Returns:
        List of heading candidates with properties
    """
    doc = pymupdf.open(pdf_path)
    heading_candidates = []

    # Patterns to exclude (non-heading content)
    exclude_patterns = [
        r'^\d{4}-\d{2}-\d{2}',  # Dates
        r'^Page\s+\d+',  # Page numbers
        r'^Copyright\s*©',  # Copyright notices
        r'^\d+\s*$',  # Just numbers
        r'^[A-Z]{2,}\s*\d{4}',  # Document codes like "AD 2022"
        r'^\w+@\w+\.\w+',  # Email addresses
        r'^https?://',  # URLs
        r'^\.\.\.',  # Ellipsis/continuation
        r'^[\d\.\s]+$',  # Only numbers and dots
    ]

    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict")["blocks"]
        page_height = page.rect.height

        for block in blocks:
            if "lines" not in block:
                continue

            for line in block["lines"]:
                # Concatenate all spans in the line to get full text
                line_text = ""
                line_properties = []

                for span in line["spans"]:
                    text = span["text"].strip()
                    # skip completely empty spans
                    if text == "":
                        continue
                    line_text += text + " "
                    line_properties.append({
                        "size": round(span["size"], 2),
                        "flags": span["flags"],
                        "font": span["font"],
                        "color": span.get("color", 0)
                    })

                line_text = line_text.strip()

                if not line_text:
                    continue

                # Skip if matches exclude patterns
                skip = False
                for pattern in exclude_patterns:
                    if re.match(pattern, line_text, re.IGNORECASE):
                        skip = True
                        break

                if skip:
                    continue

                # Skip very short or very long text
                if len(line_text) < 3 or len(line_text) > 150:
                    continue

                # Skip if mostly punctuation or numbers
                alphanumeric = sum(c.isalnum() for c in line_text)
                if alphanumeric < len(line_text) * 0.5:
                    continue

                # Use the first span's properties as representative
                if line_properties:
                    primary_props = line_properties[0]

                    # Check if it looks like a heading (bold or larger font)
                    # Bold flag in MuPDF: flags bit 4 (value 16) often indicates bold
                    is_bold = bool(primary_props["flags"] & 16)

                    # Get position on page (for filtering headers/footers)
                    y_pos = line["bbox"][1]
                    is_header = y_pos < page_height * 0.1
                    is_footer = y_pos > page_height * 0.9

                    heading_candidates.append({
                        "text": line_text,
                        "page": page_num + 1,  # 1-indexed for readability
                        "size": primary_props["size"],
                        "flags": primary_props["flags"],
                        "is_bold": is_bold,
                        "font": primary_props["font"],
                        "color": primary_props["color"],
                        "is_header": is_header,
                        "is_footer": is_footer,
                        "bbox": {
                            "x0": line["bbox"][0],
                            "y0": line["bbox"][1],
                            "x1": line["bbox"][2],
                            "y1": line["bbox"][3]
                        }
                    })

    doc.close()
    return heading_candidates


def analyze_font_patterns(heading_candidates):
    """
    Analyze font size and style patterns to identify likely headings.

    Args:
        heading_candidates: List of potential headings

    Returns:
        Statistics about font usage
    """
    size_frequency = defaultdict(int)
    size_examples = defaultdict(list)

    for candidate in heading_candidates:
        size = candidate["size"]
        size_frequency[size] += 1

        if len(size_examples[size]) < 3:  # Keep up to 3 examples
            size_examples[size].append(candidate["text"])

    # Sort by size descending then frequency
    sorted_sizes = sorted(size_frequency.items(), key=lambda x: (-x[0], -x[1]))

    return {
        "size_frequency": dict(sorted_sizes),
        "size_examples": dict(size_examples),
        "unique_sizes": len(size_frequency)
    }


def assign_hierarchy_levels(heading_candidates, min_heading_size=None, max_levels=6,
                            bold_only=False, exclude_headers_footers=True):
    """
    Assign hierarchy levels to headings based on font properties.

    Args:
        heading_candidates: List of heading candidates
        min_heading_size: Minimum font size to consider as heading (auto-detect if None)
        max_levels: Maximum number of heading levels to create
        bold_only: If True, only consider bold text as headings
        exclude_headers_footers: If True, exclude text in header/footer areas

    Returns:
        List of headings with assigned levels
    """
    if not heading_candidates:
        return []

    # Filter out headers/footers if requested
    if exclude_headers_footers:
        filtered = []
        for h in heading_candidates:
            if not h.get("is_header", False) and not h.get("is_footer", False):
                filtered.append(h)
        heading_candidates = filtered

    # Auto-detect minimum heading size if not provided
    if min_heading_size is None:
        all_sizes = sorted([h["size"] for h in heading_candidates])
        # Use 75th percentile as baseline - only larger fonts are headings
        if len(all_sizes) > 0:
            percentile_75_idx = int(len(all_sizes) * 0.75)
            # clamp index
            percentile_75_idx = min(max(percentile_75_idx, 0), len(all_sizes) - 1)
            min_heading_size = all_sizes[percentile_75_idx]
        else:
            min_heading_size = 10.0

    # print min_heading_size for debugging
    print(f"Auto-detected minimum heading size: {min_heading_size}")

    # Filter candidates
    filtered_candidates = []
    for h in heading_candidates:
        # If bold_only mode, skip non-bold text
        if bold_only and not h["is_bold"]:
            continue

        # Check size threshold
        if h["size"] >= min_heading_size:
            filtered_candidates.append(h)
        # Also include bold text that's close to threshold
        elif h["is_bold"] and h["size"] >= min_heading_size * 0.9:
            filtered_candidates.append(h)

    if not filtered_candidates:
        return []

    # Group by font size and bold status
    # Create a composite key: (size, is_bold)
    style_groups = defaultdict(list)
    for h in filtered_candidates:
        key = (round(h["size"], 1), h["is_bold"])
        style_groups[key].append(h)

    # Remove style groups with too few instances (likely not real headings)
    # Exception: keep if font size is significantly large
    max_size = max(h["size"] for h in filtered_candidates)
    filtered_style_groups = {}
    for k, v in style_groups.items():
        if len(v) >= 2 or k[0] >= max_size * 0.9:
            filtered_style_groups[k] = v
    style_groups = filtered_style_groups

    # Sort style groups by size (descending), then by bold status
    sorted_styles = sorted(style_groups.keys(), key=lambda x: (-x[0], -x[1]))

    # Assign levels (limit to max_levels)
    level_map = {}
    for level, style_key in enumerate(sorted_styles[:max_levels], start=1):
        level_map[style_key] = level

    # Build hierarchy with assigned levels
    hierarchy = []
    for candidate in filtered_candidates:
        style_key = (round(candidate["size"], 1), candidate["is_bold"])

        # Only include if style was mapped to a level
        if style_key in level_map:
            level = level_map[style_key]
            hierarchy.append({
                "text": candidate["text"],
                "level": level,
                "page": candidate["page"],
                "size": candidate["size"],
                "is_bold": candidate["is_bold"],
                "font": candidate["font"],
                "style_category": "size_{}_bold_{}".format(style_key[0], style_key[1])
            })

    return hierarchy


def build_parent_child_tree(hierarchy):
    """
    Convert flat hierarchy list into parent-child tree structure.

    Args:
        hierarchy: List of headings with levels

    Returns:
        List of root nodes with nested children
    """
    if not hierarchy:
        return []

    # Add unique IDs to each heading
    for i, heading in enumerate(hierarchy):
        heading["id"] = "heading_{}".format(i)

    tree = []
    stack = []  # Stack to track parent at each level

    for heading in hierarchy:
        level = heading["level"]

        # Create node with children array
        node = {
            "id": heading["id"],
            "text": heading["text"],
            "level": level,
            "page": heading["page"],
            "size": heading.get("size"),
            "is_bold": heading.get("is_bold"),
            "font": heading.get("font"),
            "children": []
        }

        # Remove items from stack that are at same or deeper level
        while stack and stack[-1]["level"] >= level:
            stack.pop()

        # Add node to parent's children or to root
        if stack:
            stack[-1]["children"].append(node)
        else:
            tree.append(node)

        # Add current node to stack
        stack.append(node)

    return tree


def tree_to_nested_dict(tree):
    """
    Convert hierarchy_tree (list of nested nodes) into nested dictionary format like:
    {
      "Section A": {
        "Subsection 1": {},
        "Subsection 2": {}
      },
      "Section B": {}
    }
    """
    result = {}
    for node in tree:
        # Strip or normalize node text if needed (currently keep as-is)
        key = node["text"]
        if node.get("children"):
            result[key] = tree_to_nested_dict(node["children"])
        else:
            result[key] = {}
    return result


def generate_hierarchy_json(pdf_path, output_json_path=None, min_heading_size=None,
                            max_levels=6, bold_only=False, exclude_headers_footers=True):
    """
    Extract heading hierarchy from PDF and save as nested JSON.

    Args:
        pdf_path: Path to PDF file
        output_json_path: Path to save JSON (optional)
        min_heading_size: Minimum font size for headings (auto-detect if None)
        max_levels: Maximum heading levels
        bold_only: If True, only consider bold text as headings
        exclude_headers_footers: If True, exclude text in header/footer areas

    Returns:
        Nested dict representing the document section hierarchy
    """
    print("Processing: {}".format(pdf_path))

    # Extract candidates
    candidates = extract_heading_candidates_from_pdf(pdf_path)
    print("Found {} potential heading candidates".format(len(candidates)))

    # Analyze patterns
    patterns = analyze_font_patterns(candidates)
    print("Detected {} unique font sizes".format(patterns['unique_sizes']))

    # Assign hierarchy
    hierarchy = assign_hierarchy_levels(
        candidates,
        min_heading_size,
        max_levels,
        bold_only,
        exclude_headers_footers
    )
    print("Assigned {} headings to hierarchy".format(len(hierarchy)))

    # Build parent-child tree
    tree = build_parent_child_tree(hierarchy)

    # Convert tree to nested JSON
    nested_json = tree_to_nested_dict(tree)

    # Save to file if path provided
    if output_json_path:
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(nested_json, f, indent=2, ensure_ascii=False)
        print("✅ Saved clean hierarchy JSON to: {}".format(output_json_path))

    return nested_json


def print_tree_recursive(node, indent=0, max_text_len=60):
    """Recursively print tree structure (useful for debugging)."""
    marker = "#" * node["level"]
    indent_str = "  " * indent
    text = node["text"][:max_text_len]
    print("Page {:3d} | {:6s} | {}{}".format(node['page'], marker, indent_str, text))

    for child in node["children"]:
        print_tree_recursive(child, indent + 1, max_text_len)


def print_hierarchy_preview(hierarchy_data, max_items=20):
    """
    Print a preview of the hierarchy for quick inspection.
    Accepts the nested JSON returned by generate_hierarchy_json, but also prints
    some summary info extracted from the original pipeline if needed.
    """
    # If hierarchy_data is nested dict, pretty print top-level keys
    if isinstance(hierarchy_data, dict):
        print("\n" + "=" * 80)
        print("HIERARCHY PREVIEW (Top-level sections)")
        print("=" * 80)
        top_keys = list(hierarchy_data.keys())
        for i, k in enumerate(top_keys[:max_items]):
            print(f"{i+1:3d}. {k}")
        if len(top_keys) > max_items:
            print(f"... and {len(top_keys) - max_items} more top-level sections")
        print("=" * 80 + "\n")
    else:
        # Fallback: just print raw
        print(json.dumps(hierarchy_data, indent=2, ensure_ascii=False))


def find_pdf_files(data_directory):
    """
    Recursively find all PDF files in the data directory.
    
    Args:
        data_directory: Path to the data directory
    
    Returns:
        List of tuples (pdf_file_path, relative_path_from_data_dir)
    """
    pdf_files = []
    data_path = Path(data_directory)
    
    if not data_path.exists():
        print(f"Warning: Data directory {data_directory} does not exist")
        return pdf_files
    
    # Recursively find all PDF files
    for pdf_file in data_path.rglob("*.pdf"):
        # Get the relative path from the data directory
        relative_path = pdf_file.relative_to(data_path)
        pdf_files.append((str(pdf_file), str(relative_path)))
    
    return pdf_files


def create_output_path(pdf_relative_path, output_base_dir):
    """
    Create the output path for a PDF file, maintaining directory structure.
    
    Args:
        pdf_relative_path: Relative path of PDF from data directory
        output_base_dir: Base output directory
    
    Returns:
        Tuple of (output_json_path, output_directory)
    """
    pdf_path = Path(pdf_relative_path)
    
    # Change extension from .pdf to .json
    json_filename = pdf_path.stem + ".json"
    
    # Create output path maintaining directory structure
    output_json_path = Path(output_base_dir) / pdf_path.parent / json_filename
    output_directory = output_json_path.parent
    
    return str(output_json_path), str(output_directory)


def batch_process_pdfs(data_directory=None, output_base_dir="./section_hierarchy_pdfs", 
                       min_heading_size=None, max_levels=6, bold_only=False, 
                       exclude_headers_footers=True):
    """
    Batch process all PDFs in the data directory and save section hierarchy JSONs.
    
    Args:
        data_directory: Path to data directory (uses config if None)
        output_base_dir: Base directory for output JSON files
        min_heading_size: Minimum font size for headings (auto-detect if None)
        max_levels: Maximum heading levels
        bold_only: If True, only consider bold text as headings
        exclude_headers_footers: If True, exclude text in header/footer areas
    
    Returns:
        Dictionary with processing statistics
    """
    if data_directory is None:
        data_directory = DATA_DIRECTORY
    
    print(f"Starting batch processing of PDFs from: {data_directory}")
    print(f"Output directory: {output_base_dir}")
    print("=" * 80)
    
    # Find all PDF files
    pdf_files = find_pdf_files(data_directory)
    
    if not pdf_files:
        print(f"No PDF files found in {data_directory}")
        return {"total_files": 0, "processed": 0, "failed": 0, "skipped": 0}
    
    print(f"Found {len(pdf_files)} PDF files to process")
    
    # Statistics tracking
    stats = {"total_files": len(pdf_files), "processed": 0, "failed": 0, "skipped": 0}
    
    for i, (pdf_path, relative_path) in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}] Processing: {relative_path}")
        
        try:
            # Create output path
            output_json_path, output_dir = create_output_path(relative_path, output_base_dir)
            
            # Check if output already exists
            if os.path.exists(output_json_path):
                print(f"  ⚠️  JSON already exists: {output_json_path}")
                response = input("  Overwrite? (y/N): ").lower().strip()
                if response != 'y':
                    print(f"  ⏭️  Skipped: {relative_path}")
                    stats["skipped"] += 1
                    continue
            
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Process the PDF
            nested_json = generate_hierarchy_json(
                pdf_path=pdf_path,
                output_json_path=output_json_path,
                min_heading_size=min_heading_size,
                max_levels=max_levels,
                bold_only=bold_only,
                exclude_headers_footers=exclude_headers_footers
            )
            
            print(f"  ✅ Successfully processed: {relative_path}")
            print(f"     Saved to: {output_json_path}")
            
            # Show brief preview
            if isinstance(nested_json, dict) and nested_json:
                top_sections = list(nested_json.keys())[:3]
                print(f"     Top sections: {', '.join(top_sections)}")
                if len(nested_json) > 3:
                    print(f"     ... and {len(nested_json) - 3} more sections")
            
            stats["processed"] += 1
            
        except Exception as e:
            print(f"  ❌ Failed to process {relative_path}: {str(e)}")
            stats["failed"] += 1
    
    # Print final statistics
    print("\n" + "=" * 80)
    print("BATCH PROCESSING COMPLETED")
    print("=" * 80)
    print(f"Total files found: {stats['total_files']}")
    print(f"Successfully processed: {stats['processed']}")
    print(f"Failed: {stats['failed']}")
    print(f"Skipped: {stats['skipped']}")
    print("=" * 80)
    
    return stats



