import difflib
import re
from pathlib import Path
import unicodedata
import csv

def remove_table_of_contents(text):
    """
    Remove Table of Contents sections which often differ in structure.
    """
    # Pattern 1: Remove explicit "Table of Contents" sections
    # This looks for "Table of Contents" or "Table Of Contents" followed by content until next major section
    text = re.sub(
        r'table\s+of\s+contents.*?(?=^#|\n\n[A-Z]|\Z)',
        '',
        text,
        flags=re.IGNORECASE | re.DOTALL | re.MULTILINE
    )
    
    # Pattern 2: Remove TOC-style page number references (e.g., "Something ... 42")
    text = re.sub(r'\s+\.{2,}\s*\d+\s*', ' ', text)
    
    # Pattern 3: Remove lines that are just section titles with page numbers
    lines = text.split('\n')
    filtered_lines = []
    for line in lines:
        # Skip lines that look like TOC entries (text followed by numbers)
        if re.match(r'^[A-Z][^\.]+\s+\d+\s*$', line.strip()):
            continue
        filtered_lines.append(line)
    text = '\n'.join(filtered_lines)
    
    return text

def normalize_tables(text):
    """
    Convert both HTML and Markdown tables to a normalized format.
    """
    # Remove HTML table tags but keep content
    text = re.sub(r'<table[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</table>', '', text, flags=re.IGNORECASE)
    
    # Remove caption tags but keep content
    text = re.sub(r'<caption>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</caption>', '', text, flags=re.IGNORECASE)
    
    # Remove tbody, thead, tfoot tags
    text = re.sub(r'</?tbody[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</?thead[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</?tfoot[^>]*>', '', text, flags=re.IGNORECASE)
    
    # Convert table rows - remove tr tags but keep content
    text = re.sub(r'<tr[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</tr>', '', text, flags=re.IGNORECASE)
    
    # Convert table cells - remove td/th tags but keep content
    text = re.sub(r'<td[^>]*>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'</td>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'<th[^>]*>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'</th>', ' ', text, flags=re.IGNORECASE)
    
    # Remove markdown table separators (e.g., |---|---|)
    text = re.sub(r'\|[\s\-:]+\|', '', text)
    
    # Remove markdown table pipes but keep content
    text = re.sub(r'\|', ' ', text)
    
    return text

def normalize_text(text):
    """
    Aggressively normalize text to focus on actual content, not formatting.
    """
    # First, remove Table of Contents
    text = remove_table_of_contents(text)
    
    # Normalize tables (both HTML and Markdown)
    text = normalize_tables(text)
    
    # Remove HTML comments completely
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    
    # Remove code blocks
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    
    # Remove markdown formatting
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'\1', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'___(.+?)___', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    text = re.sub(r'!\[.*?\]\(.+?\)', '', text)
    text = re.sub(r'^[-*_]{3,}$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    
    # Normalize unicode characters
    text = unicodedata.normalize('NFKD', text)
    
    # Replace common symbol variations
    symbol_map = {
        '™': 'TM',
        'â„¢': 'TM',
        '®': 'R',
        '©': 'C',
        'Â©': 'C',
        '…': '...',
        '—': '--',
        '–': '-',
        '"': '"',
        '"': '"',
        ''': "'",
        ''': "'",
        '•': '*',
        'Â°': ' degrees',
        'Ã—': 'x',
        'Â': '',
        'ï¿½': '',
        '\u00a0': ' ',
        'Âº': ' degrees',
        'â€˜': "'",
        'â€™': "'",
        'â€œ': '"',
        'â€': '"',
    }
    for symbol, replacement in symbol_map.items():
        text = text.replace(symbol, replacement)
    
    # Normalize all whitespace
    text = re.sub(r'\n\s*\n+', '\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    lines = [line.strip() for line in text.split('\n')]
    lines = [line for line in lines if line]
    text = '\n'.join(lines)
    
    text = text.strip()
    
    return text

def get_word_list(text):
    """Extract words from text, ignoring punctuation differences."""
    words = re.findall(r'\b[\w]+\b', text.lower())
    return words

def calculate_character_accuracy(gold_text, ocr_text):
    """Calculate character-level accuracy using sequence matching."""
    matcher = difflib.SequenceMatcher(None, gold_text, ocr_text)
    matching_chars = sum(block.size for block in matcher.get_matching_blocks())
    total_chars = len(gold_text)
    
    if total_chars == 0:
        return 0.0
    
    accuracy = (matching_chars / total_chars) * 100
    return accuracy

def calculate_word_accuracy(gold_text, ocr_text):
    """Calculate word-level accuracy."""
    gold_words = get_word_list(gold_text)
    ocr_words = get_word_list(ocr_text)
    
    matcher = difflib.SequenceMatcher(None, gold_words, ocr_words)
    matching_words = sum(block.size for block in matcher.get_matching_blocks())
    total_words = len(gold_words)
    
    if total_words == 0:
        return 0.0
    
    accuracy = (matching_words / total_words) * 100
    return accuracy

def get_detailed_word_errors(gold_text, ocr_text):
    """Get all word-level errors."""
    gold_words = get_word_list(gold_text)
    ocr_words = get_word_list(ocr_text)
    
    matcher = difflib.SequenceMatcher(None, gold_words, ocr_words)
    errors = []
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != 'equal':
            # Get context (5 words before and after)
            context_before_gold = ' '.join(gold_words[max(0, i1-5):i1])
            context_after_gold = ' '.join(gold_words[i2:min(len(gold_words), i2+5)])
            context_before_ocr = ' '.join(ocr_words[max(0, j1-5):j1])
            context_after_ocr = ' '.join(ocr_words[j2:min(len(ocr_words), j2+5)])
            
            gold_text_segment = ' '.join(gold_words[i1:i2]) if i1 < i2 else ''
            ocr_text_segment = ' '.join(ocr_words[j1:j2]) if j1 < j2 else ''
            
            errors.append({
                'error_type': tag,
                'position_gold': i1,
                'position_ocr': j1,
                'gold_text': gold_text_segment,
                'ocr_text': ocr_text_segment,
                'context_before_gold': context_before_gold,
                'context_after_gold': context_after_gold,
                'context_before_ocr': context_before_ocr,
                'context_after_ocr': context_after_ocr,
                'gold_words_affected': i2 - i1 if i2 > i1 else 0,
                'ocr_words_affected': j2 - j1 if j2 > j1 else 0
            })
    
    return errors

def save_errors_to_csv(errors, output_file):
    """Save detailed errors to a CSV file."""
    if not errors:
        print(f"\nNo errors to save.")
        return
    
    fieldnames = [
        'error_number',
        'error_type',
        'position_gold',
        'position_ocr',
        'gold_text',
        'ocr_text',
        'context_before_gold',
        'context_after_gold',
        'context_before_ocr',
        'context_after_ocr',
        'gold_words_affected',
        'ocr_words_affected'
    ]
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for i, error in enumerate(errors, 1):
            row = {'error_number': i}
            row.update(error)
            writer.writerow(row)
    
    print(f"\n✓ Detailed errors saved to: {output_file}")

def compare_markdown_files(gold_path, ocr_path, save_csv=True):
    """Main function to compare gold and OCR markdown files."""
    # Read files
    with open(gold_path, 'r', encoding='utf-8') as f:
        gold_content = f.read()
    
    with open(ocr_path, 'r', encoding='utf-8') as f:
        ocr_content = f.read()
    
    # Extract raw text with normalization
    gold_text = normalize_text(gold_content)
    ocr_text = normalize_text(ocr_content)
    
    # Get word lists
    gold_words = get_word_list(gold_text)
    ocr_words = get_word_list(ocr_text)
    
    # Calculate accuracies
    char_accuracy = calculate_character_accuracy(gold_text, ocr_text)
    word_accuracy = calculate_word_accuracy(gold_text, ocr_text)
    
    # Get all error details
    errors = get_detailed_word_errors(gold_text, ocr_text)
    
    # Calculate statistics
    total_errors = len(errors)
    error_types = {'replace': 0, 'delete': 0, 'insert': 0}
    for error in errors:
        error_types[error['error_type']] = error_types.get(error['error_type'], 0) + 1
    
    # Generate report
    print("=" * 80)
    print("MARKDOWN OCR ACCURACY REPORT (NORMALIZED)")
    print("=" * 80)
    print(f"\nGold file: {gold_path}")
    print(f"OCR file:  {ocr_path}")
    print("\n" + "-" * 80)
    print("NORMALIZATION APPLIED:")
    print("-" * 80)
    print("✓ Table of Contents sections removed")
    print("✓ HTML tables converted to plain text (tags removed)")
    print("✓ Markdown tables converted to plain text (pipes removed)")
    print("✓ HTML comments removed")
    print("✓ Whitespace normalized (multiple spaces/newlines → single)")
    print("✓ Special characters standardized (™→TM, ©→C, °→degrees)")
    print("✓ Markdown formatting stripped")
    print("✓ Case normalized for comparison")
    print("\n" + "-" * 80)
    print("STATISTICS")
    print("-" * 80)
    print(f"Gold text length:     {len(gold_text)} characters, {len(gold_words)} words")
    print(f"OCR text length:      {len(ocr_text)} characters, {len(ocr_words)} words")
    print(f"Length difference:    {abs(len(gold_text) - len(ocr_text))} characters, {abs(len(gold_words) - len(ocr_words))} words")
    print(f"\nCharacter Accuracy:   {char_accuracy:.2f}%")
    print(f"Word Accuracy:        {word_accuracy:.2f}%")
    print(f"\nTotal word errors:    {total_errors}")
    print(f"  - Replacements:     {error_types.get('replace', 0)}")
    print(f"  - Deletions:        {error_types.get('delete', 0)}")
    print(f"  - Insertions:       {error_types.get('insert', 0)}")
    
    # Display first 20 errors
    if errors:
        print("\n" + "-" * 80)
        print(f"WORD-LEVEL ERROR EXAMPLES (showing first 20 of {total_errors})")
        print("-" * 80)
        for i, error in enumerate(errors[:20], 1):
            print(f"\n{i}. Type: {error['error_type'].upper()}")
            print(f"   Position: Gold word {error['position_gold']}, OCR word {error['position_ocr']}")
            if error['gold_text']:
                print(f"   Gold:     '{error['gold_text']}'")
            if error['ocr_text']:
                print(f"   OCR:      '{error['ocr_text']}'")
            print(f"   Context:  ...{error['context_before_gold']} [{error['gold_text'] or 'DELETED'}] {error['context_after_gold']}...")
            print(f"             ...{error['context_before_ocr']} [{error['ocr_text'] or 'MISSING'}] {error['context_after_ocr']}...")
    
    print("\n" + "=" * 80)
    print("INTERPRETATION:")
    print("-" * 80)
    if word_accuracy >= 95:
        print("✓ Excellent OCR quality - Very few recognition errors")
    elif word_accuracy >= 90:
        print("✓ Good OCR quality - Minor errors present")
    elif word_accuracy >= 80:
        print("⚠ Fair OCR quality - Noticeable errors, review recommended")
    else:
        print("✗ Poor OCR quality - Significant errors, manual review needed")
    
    print("\n" + "-" * 80)
    print("NOTE:")
    print("-" * 80)
    print("This comparison focuses on text content accuracy, ignoring:")
    print("  • Table of Contents sections")
    print("  • Table structure differences (HTML vs Markdown)")
    print("  • Formatting differences (headers, lists, emphasis)")
    print("  • Whitespace variations")
    print("  • Special character encoding variants")
    print("=" * 80)
    
    # Save detailed errors to CSV
    if save_csv and errors:
        csv_filename = Path(ocr_path).stem + '_errors.csv'
        save_errors_to_csv(errors, csv_filename)
    
    return {
        'character_accuracy': char_accuracy,
        'word_accuracy': word_accuracy,
        'total_errors': total_errors,
        'error_breakdown': error_types,
        'gold_char_count': len(gold_text),
        'ocr_char_count': len(ocr_text),
        'gold_word_count': len(gold_words),
        'ocr_word_count': len(ocr_words),
        'errors': errors
    }

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python script.py <gold_markdown_path> <ocr_markdown_path> [--no-csv]")
        print("\nExample:")
        print("  python script.py gold.md ocr_extracted.md")
        print("  python script.py gold.md ocr_extracted.md --no-csv")
        sys.exit(1)
    
    gold_file = sys.argv[1]
    ocr_file = sys.argv[2]
    save_csv = '--no-csv' not in sys.argv
    
    # Check if files exist
    if not Path(gold_file).exists():
        print(f"Error: Gold file '{gold_file}' not found!")
        sys.exit(1)
    
    if not Path(ocr_file).exists():
        print(f"Error: OCR file '{ocr_file}' not found!")
        sys.exit(1)
    
    # Compare files
    results = compare_markdown_files(gold_file, ocr_file, save_csv=save_csv)