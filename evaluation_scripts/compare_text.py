import difflib
import re
from pathlib import Path
import json

def get_word_list(text):
    """Extract words from text."""
    words = re.findall(r'\b[\w]+\b', text)
    return words

def calculate_character_accuracy(gold_text, ocr_text):
    """Calculate character-level accuracy using sequence matching."""
    matcher = difflib.SequenceMatScher(None, gold_text, ocr_text)
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

def save_differences_to_json(differences, output_file):
    """Save detailed differences to a JSON file."""
    if not differences:
        print(f"\nNo differences to save.")
        return
    
    # Update the fieldnames in the data to match
    updated_differences = []
    for i, diff in enumerate(differences, 1):
        updated_diff = {
            'difference_number': i,
            'difference_type': diff['error_type'],
            'position_file1': diff['position_gold'],
            'position_file2': diff['position_ocr'],
            'file1_text': diff['gold_text'],
            'file2_text': diff['ocr_text'],
            'context_before_file1': diff['context_before_gold'],
            'context_after_file1': diff['context_after_gold'],
            'context_before_file2': diff['context_before_ocr'],
            'context_after_file2': diff['context_after_ocr'],
            'file1_words_affected': diff['gold_words_affected'],
            'file2_words_affected': diff['ocr_words_affected']
        }
        updated_differences.append(updated_diff)
    
    with open(output_file, 'w', encoding='utf-8') as jsonfile:
        json.dump(updated_differences, jsonfile, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Detailed differences saved to: {output_file}")

def compare_markdown_files(file1_path, file2_path, save_json=True):
    """Main function to compare two markdown files."""
    # Read files
    with open(file1_path, 'r', encoding='utf-8') as f:
        file1_content = f.read()
    
    with open(file2_path, 'r', encoding='utf-8') as f:
        file2_content = f.read()
    
    # Use raw content without any normalization
    file1_text = file1_content
    file2_text = file2_content
    
    # Get word lists
    file1_words = get_word_list(file1_text)
    file2_words = get_word_list(file2_text)
    
    # Calculate similarities
    char_accuracy = calculate_character_accuracy(file1_text, file2_text)
    word_accuracy = calculate_word_accuracy(file1_text, file2_text)
    
    # Get all difference details
    errors = get_detailed_word_errors(file1_text, file2_text)
    
    # Calculate statistics
    total_errors = len(errors)
    error_types = {'replace': 0, 'delete': 0, 'insert': 0}
    for error in errors:
        error_types[error['error_type']] = error_types.get(error['error_type'], 0) + 1
    
    # Generate report
    print("=" * 80)
    print("MARKDOWN COMPARISON REPORT")
    print("=" * 80)
    print(f"\nFile 1: {file1_path}")
    print(f"File 2: {file2_path}")
    print("\n" + "-" * 80)
    print("STATISTICS")
    print("-" * 80)
    print(f"File1 text length:    {len(file1_text)} characters, {len(file1_words)} words")
    print(f"File2 text length:    {len(file2_text)} characters, {len(file2_words)} words")
    print(f"Length difference:    {abs(len(file1_text) - len(file2_text))} characters, {abs(len(file1_words) - len(file2_words))} words")
    print(f"\nCharacter Similarity: {char_accuracy:.2f}%")
    print(f"Word Similarity:      {word_accuracy:.2f}%")
    print(f"\nTotal word differences: {total_errors}")
    print(f"  - Replacements:     {error_types.get('replace', 0)}")
    print(f"  - Deletions:        {error_types.get('delete', 0)}")
    print(f"  - Insertions:       {error_types.get('insert', 0)}")
    
    # Display first 20 differences
    if errors:
        print("\n" + "-" * 80)
        print(f"WORD-LEVEL DIFFERENCE EXAMPLES (showing first 20 of {total_errors})")
        print("-" * 80)
        for i, error in enumerate(errors[:20], 1):
            print(f"\n{i}. Type: {error['error_type'].upper()}")
            print(f"   Position: File1 word {error['position_gold']}, File2 word {error['position_ocr']}")
            if error['gold_text']:
                print(f"   File1:    '{error['gold_text']}'")
            if error['ocr_text']:
                print(f"   File2:    '{error['ocr_text']}'")
            print(f"   Context:  ...{error['context_before_gold']} [{error['gold_text'] or 'DELETED'}] {error['context_after_gold']}...")
            print(f"             ...{error['context_before_ocr']} [{error['ocr_text'] or 'MISSING'}] {error['context_after_ocr']}...")
    
    print("\n" + "=" * 80)
    print("INTERPRETATION:")
    print("-" * 80)
    if word_accuracy >= 95:
        print("✓ Excellent similarity - Very few differences")
    elif word_accuracy >= 90:
        print("✓ Good similarity - Minor differences present")
    elif word_accuracy >= 80:
        print("⚠ Fair similarity - Noticeable differences, review recommended")
    else:
        print("✗ Poor similarity - Significant differences, manual review needed")
    
    print("\n" + "-" * 80)
    print("NOTE:")
    print("-" * 80)
    print("This is a direct comparison of the two markdown files with no preprocessing or normalization applied.")
    print("=" * 80)
    
    # Save detailed differences to JSON
    if save_json and errors:
        json_filename = Path(file2_path).stem + '_differences.json'
        save_differences_to_json(errors, json_filename)
    
    return {
        'character_similarity': char_accuracy,
        'word_similarity': word_accuracy,
        'total_differences': total_errors,
        'difference_breakdown': error_types,
        'file1_char_count': len(file1_text),
        'file2_char_count': len(file2_text),
        'file1_word_count': len(file1_words),
        'file2_word_count': len(file2_words),
        'differences': errors
    }

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python script.py <markdown_file_1> <markdown_file_2> [--no-json]")
        print("\nExample:")
        print("  python script.py file1.md file2.md")
        print("  python script.py file1.md file2.md --no-json")
        sys.exit(1)
    
    file1 = sys.argv[1]
    file2 = sys.argv[2]
    save_json = '--no-json' not in sys.argv
    
    # Check if files exist
    if not Path(file1).exists():
        print(f"Error: File '{file1}' not found!")
        sys.exit(1)
    
    if not Path(file2).exists():
        print(f"Error: File '{file2}' not found!")
        sys.exit(1)
    
    # Compare files
    results = compare_markdown_files(file1, file2, save_json=save_json)