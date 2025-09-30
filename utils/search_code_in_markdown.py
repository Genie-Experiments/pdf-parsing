import re
import difflib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Handle both relative and absolute imports
try:
    from .get_markdown_file_path import get_markdown_file_path
except ImportError:
    from get_markdown_file_path import get_markdown_file_path


def normalize_text_variants(json_code_text: str) -> List[str]:
    """
    Create multiple normalized variants of JSON code text for matching.
    
    Args:
        json_code_text: Raw code text from JSON file
        
    Returns:
        List of normalized text variants to try for matching
    """
    variants = []
    
    # Original text
    variants.append(json_code_text)
    
    # Replace newlines with spaces (most common case)
    variant1 = json_code_text.replace('\n', ' ')
    variants.append(variant1)
    
    # Replace newlines with spaces and normalize whitespace
    variant2 = re.sub(r'\s+', ' ', variant1).strip()
    variants.append(variant2)
    
    # Remove newlines entirely
    variant3 = json_code_text.replace('\n', '')
    variants.append(variant3)
    
    # Handle escape sequences
    variant4 = json_code_text.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
    if variant4 != json_code_text:
        variants.append(variant4)
        # Also try the escaped version with newlines as spaces
        variants.append(variant4.replace('\n', ' '))
    
    # Handle special unicode characters (like soft hyphens)
    variant5 = json_code_text.replace('\xad', '­')  # Convert to actual soft hyphen
    if variant5 != json_code_text:
        variants.append(variant5)
        variants.append(variant5.replace('\n', ' '))
    
    # Replace soft hyphens with regular hyphens
    variant6 = json_code_text.replace('\xad', '-')
    if variant6 != json_code_text:
        variants.append(variant6)
        variants.append(variant6.replace('\n', ' '))
    
    # Remove duplicates while preserving order
    unique_variants = []
    seen = set()
    for variant in variants:
        if variant and variant not in seen:
            unique_variants.append(variant)
            seen.add(variant)
    
    return unique_variants


def find_best_fuzzy_match(target_text: str, markdown_content: str, 
                         similarity_threshold: float = 0.8) -> Optional[Dict]:
    """
    Find the best fuzzy match for target text in markdown content.
    
    Args:
        target_text: Text to search for
        markdown_content: Content to search in
        similarity_threshold: Minimum similarity score (0.0 to 1.0)
        
    Returns:
        Dictionary with match details or None if no good match found
    """
    # Skip fuzzy matching for very long texts (too expensive)
    if len(target_text) > 500:
        return None
    
    # Split into reasonable chunks for comparison
    words = target_text.split()
    if len(words) < 3 or len(words) > 50:  # Skip very short or very long texts
        return None
    
    # Create sliding windows of text in markdown
    md_words = markdown_content.split()
    window_size = len(words)
    
    # Limit the number of windows to check for performance
    max_windows = min(1000, len(md_words) - window_size + 1)
    if max_windows <= 0:
        return None
    
    best_match = None
    best_score = 0
    
    # Try different window sizes around the target length
    for size_variation in [0, -1, 1]:  # Reduced variations for speed
        current_size = window_size + size_variation
        if current_size <= 2:
            continue
            
        # Sample windows rather than checking all (for performance)
        step_size = max(1, (len(md_words) - current_size) // max_windows)
        
        for i in range(0, min(max_windows * step_size, len(md_words) - current_size + 1), step_size):
            window_text = ' '.join(md_words[i:i + current_size])
            
            # Quick length check before expensive similarity calculation
            len_diff = abs(len(target_text) - len(window_text)) / max(len(target_text), len(window_text))
            if len_diff > 0.5:  # Skip if length difference is too large
                continue
            
            # Calculate similarity using difflib
            try:
                similarity = difflib.SequenceMatcher(None, target_text.lower(), window_text.lower()).ratio()
            except:
                continue  # Skip on any error
            
            if similarity > best_score and similarity >= similarity_threshold:
                best_score = similarity
                
                # Find the exact position in original markdown
                start_pos = markdown_content.lower().find(window_text.lower())
                if start_pos != -1:
                    end_pos = start_pos + len(window_text)
                    line_num = markdown_content[:start_pos].count('\n') + 1
                    
                    best_match = {
                        'matched_text': markdown_content[start_pos:end_pos],
                        'similarity_score': similarity,
                        'start_position': start_pos,
                        'end_position': end_pos,
                        'line_number': line_num,
                        'match_type': 'fuzzy'
                    }
                    
                    # If we found a very good match, stop searching
                    if similarity > 0.95:
                        break
        
        # If we found a very good match, stop trying other sizes
        if best_match and best_match['similarity_score'] > 0.95:
            break
    
    return best_match


def search_code_in_markdown(json_code_text: str, json_file_path: str, 
                          similarity_threshold: float = 0.8) -> Optional[Dict]:
    """
    Search for code from JSON in the corresponding markdown file.
    
    This function handles the intelligent matching between JSON code blocks and
    their representation in markdown files, accounting for formatting differences
    like escaped characters, newlines, and spacing variations.
    
    Args:
        json_code_text: Raw text from JSON file code block
        json_file_path: Path to the JSON file (to find corresponding markdown)
        similarity_threshold: Minimum similarity score for fuzzy matching (0.0 to 1.0)
    
    Returns:
        Dictionary with match details:
        {
            'found': bool,
            'matched_text': str,  # Actual text found in markdown
            'similarity_score': float,  # 1.0 for exact, lower for fuzzy
            'start_position': int,  # Character position in markdown
            'end_position': int,    # End character position
            'line_number': int,     # Line number in markdown file
            'match_type': str,      # 'exact' or 'fuzzy'
            'search_variant': str,  # Which normalization variant worked
            'markdown_file_path': str
        }
        
        Returns None if no suitable match is found.
    """
    
    if not json_code_text or not json_code_text.strip():
        return None
    
    # Get corresponding markdown file path
    try:
        markdown_file_path = get_markdown_file_path(json_file_path)
        if not Path(markdown_file_path).exists():
            return None
    except Exception:
        return None
    
    # Read markdown content
    try:
        with open(markdown_file_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
    except Exception:
        return None
    
    if not markdown_content.strip():
        return None
    
    # Generate normalized variants of the JSON code text
    variants = normalize_text_variants(json_code_text.strip())
    
    # Try exact matches first (fastest)
    for i, variant in enumerate(variants):
        if not variant:
            continue
            
        # Case-sensitive exact match
        pos = markdown_content.find(variant)
        if pos != -1:
            line_num = markdown_content[:pos].count('\n') + 1
            return {
                'found': True,
                'matched_text': variant,
                'similarity_score': 1.0,
                'start_position': pos,
                'end_position': pos + len(variant),
                'line_number': line_num,
                'match_type': 'exact',
                'search_variant': f'variant_{i}',
                'markdown_file_path': str(markdown_file_path)
            }
        
        # Case-insensitive exact match
        lower_content = markdown_content.lower()
        lower_variant = variant.lower()
        pos = lower_content.find(lower_variant)
        if pos != -1:
            line_num = markdown_content[:pos].count('\n') + 1
            actual_text = markdown_content[pos:pos + len(variant)]
            return {
                'found': True,
                'matched_text': actual_text,
                'similarity_score': 1.0,
                'start_position': pos,
                'end_position': pos + len(variant),
                'line_number': line_num,
                'match_type': 'exact_case_insensitive',
                'search_variant': f'variant_{i}_lower',
                'markdown_file_path': str(markdown_file_path)
            }
    
    # Try fuzzy matching for moderate-length texts only (slower but more flexible)
    for i, variant in enumerate(variants):
        if not variant:
            continue
        
        # Skip fuzzy matching for very short or very long texts
        word_count = len(variant.split())
        if word_count < 3 or word_count > 30 or len(variant) > 300:
            continue
            
        fuzzy_result = find_best_fuzzy_match(variant, markdown_content, similarity_threshold)
        if fuzzy_result:
            fuzzy_result.update({
                'found': True,
                'search_variant': f'variant_{i}_fuzzy',
                'markdown_file_path': str(markdown_file_path)
            })
            return fuzzy_result
    
    # No match found
    return {
        'found': False,
        'matched_text': None,
        'similarity_score': 0.0,
        'start_position': -1,
        'end_position': -1,
        'line_number': -1,
        'match_type': 'none',
        'search_variant': 'none',
        'markdown_file_path': str(markdown_file_path)
    }


def search_multiple_code_blocks(json_file_path: str, 
                              filter_labels: List[str] = None,
                              similarity_threshold: float = 0.8) -> List[Dict]:
    """
    Search for all code blocks from a JSON file in the corresponding markdown.
    
    Args:
        json_file_path: Path to the JSON file
        filter_labels: List of labels to filter by (e.g., ['code', 'pre'])
        similarity_threshold: Minimum similarity score for fuzzy matching
        
    Returns:
        List of dictionaries with search results for each code block
    """
    import json
    
    if filter_labels is None:
        filter_labels = ['code']
    
    results = []
    
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for page in data.get('pages', []):
            page_num = page.get('page_number', 0)
            
            for element in page.get('elements', []):
                label = element.get('label', '')
                if label in filter_labels:
                    text = element.get('text', '')
                    if text and text.strip():
                        search_result = search_code_in_markdown(
                            text, json_file_path, similarity_threshold
                        )
                        
                        if search_result:
                            search_result.update({
                                'page_number': page_num,
                                'json_element': element,
                                'original_json_text': text
                            })
                            results.append(search_result)
    
    except Exception as e:
        # Return empty list on error, but could also raise exception
        pass
    
    return results


# Example usage and testing function
def test_search_function():
    """
    Test the search function with known examples.
    """
    # Test with the RESTCONF example we know works
    json_file = "Results/VOSS_eva/RESTCONFDevGuideVOSSFE_9.0_RG/recognition_json/RESTCONFDevGuideVOSSFE_9.0_RG.json"
    
    test_cases = [
        "GET\n/rest/restconf/data/openconfig­interfaces:interfaces\nHTTP/1.1\nHost: 10.68.5.64",
        # Add more test cases as needed
    ]
    
    print("=== Testing search_code_in_markdown ===")
    
    for i, test_text in enumerate(test_cases):
        print(f"\nTest case {i + 1}:")
        print(f"Input: {repr(test_text)}")
        
        result = search_code_in_markdown(test_text, json_file)
        
        if result and result['found']:
            print(f"✓ Found match!")
            print(f"  Match type: {result['match_type']}")
            print(f"  Similarity: {result['similarity_score']:.3f}")
            print(f"  Line: {result['line_number']}")
            print(f"  Matched text: {repr(result['matched_text'])}")
        else:
            print("✗ No match found")


if __name__ == "__main__":
    test_search_function()