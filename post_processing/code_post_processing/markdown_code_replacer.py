import json
import re
from typing import List, Dict, Any, Tuple, Optional
import fitz  # PyMuPDF
from post_processing.code_post_processing.pdf_code_search import search_code_in_pdf, normalize_text_for_comparison, fuzzy_match_similarity
from post_processing.code_post_processing.clean_and_format_code import clean_and_format_code
from post_processing.code_post_processing.main import find_code_blocks


def extract_original_pdf_code(pdf_path: str, json_element: Dict[str, Any], 
                             confidence_threshold: float = 0.7) -> Optional[str]:
    """
    Extract the original code from PDF by searching for the best matching text segment.
    
    Args:
        pdf_path: Path to the PDF file
        json_element: JSON element containing bbox coordinates and page info
        confidence_threshold: Minimum confidence for text extraction
        
    Returns:
        Original code text from PDF or None if not found
    """
    try:
        pdf_doc = fitz.open(pdf_path)
        page_number = json_element.get('page_number', 1)
        raw_text = json_element.get('text', '')
        
        # Get the full page text
        page = pdf_doc[page_number - 1]
        page_text = page.get_text()
        pdf_doc.close()
        
        # Find the code block in the page text using pattern matching
        original_code = find_code_in_pdf_page(page_text, raw_text)
        
        return original_code if original_code else raw_text
            
    except Exception as e:
        print(f"Error extracting PDF text: {e}")
        return json_element.get('text', '')


def find_code_in_pdf_page(page_text: str, target_code: str) -> Optional[str]:
    """
    Find the code block in PDF page text by looking for the pattern.
    """
    if not target_code or not page_text:
        return None
    
    # Normalize the target code for comparison
    target_lines = [line.strip() for line in target_code.split('\n') if line.strip()]
    if not target_lines:
        return None
    
    # Get page lines
    page_lines = page_text.split('\n')
    
    # Look for the first line of the code block
    first_line = target_lines[0]
    first_line_normalized = normalize_text_for_comparison(first_line)
    
    # Find potential starting points
    start_candidates = []
    for i, page_line in enumerate(page_lines):
        page_line_normalized = normalize_text_for_comparison(page_line)
        similarity = fuzzy_match_similarity(first_line_normalized, page_line_normalized)
        
        if similarity > 0.7:  # High similarity threshold
            start_candidates.append((i, similarity))
    
    # Sort candidates by similarity score
    start_candidates.sort(key=lambda x: x[1], reverse=True)
    
    # For each candidate starting point, try to extract the complete code block
    for start_idx, _ in start_candidates:
        extracted_lines = []
        
        # Extract lines that match the pattern
        for j, target_line in enumerate(target_lines):
            candidate_idx = start_idx + j
            
            if candidate_idx >= len(page_lines):
                break
                
            page_line = page_lines[candidate_idx].strip()
            target_normalized = normalize_text_for_comparison(target_line)
            page_normalized = normalize_text_for_comparison(page_line)
            
            # Check similarity
            line_similarity = fuzzy_match_similarity(target_normalized, page_normalized)
            
            if line_similarity > 0.6:  # Accept reasonably similar lines
                extracted_lines.append(page_lines[candidate_idx].rstrip())
            else:
                # Try to find the line within a small window
                found_alternative = False
                for k in range(max(0, candidate_idx-2), min(len(page_lines), candidate_idx+3)):
                    alt_line = page_lines[k].strip()
                    alt_normalized = normalize_text_for_comparison(alt_line)
                    alt_similarity = fuzzy_match_similarity(target_normalized, alt_normalized)
                    
                    if alt_similarity > 0.7:
                        extracted_lines.append(page_lines[k].rstrip())
                        found_alternative = True
                        break
                
                if not found_alternative:
                    # If we can't find this line, stop here
                    break
        
        # Check if we got a reasonable match
        if len(extracted_lines) >= len(target_lines) * 0.7:  # At least 70% of lines found
            # Remove empty lines at the beginning and end
            while extracted_lines and not extracted_lines[0].strip():
                extracted_lines.pop(0)
            while extracted_lines and not extracted_lines[-1].strip():
                extracted_lines.pop()
            
            if extracted_lines:
                return '\n'.join(extracted_lines)
    
    # If no good match found, return None
    return None


def find_best_text_segment(page_text: str, target_text: str, 
                          window_size: int = 20) -> Optional[str]:
    """
    Find the best matching text segment in the page text.
    """
    if not target_text or not page_text:
        return None
        
    target_normalized = normalize_text_for_comparison(target_text)
    target_lines = [line.strip() for line in target_text.split('\n') if line.strip()]
    
    if not target_lines:
        return None
    
    page_lines = [line.strip() for line in page_text.split('\n')]
    
    best_score = 0
    best_segment = None
    best_start = -1
    
    # Look for consecutive matching lines
    for i in range(len(page_lines)):
        for num_lines in range(1, min(len(target_lines) + 3, window_size)):
            if i + num_lines > len(page_lines):
                break
                
            segment_lines = page_lines[i:i + num_lines]
            segment = '\n'.join(segment_lines)
            
            # Skip empty segments
            if not segment.strip():
                continue
            
            segment_normalized = normalize_text_for_comparison(segment)
            score = fuzzy_match_similarity(target_normalized, segment_normalized)
            
            # Bonus for matching number of lines
            if len(segment_lines) == len(target_lines):
                score *= 1.1
            
            # Bonus for finding key patterns
            if any(keyword in segment.lower() for keyword in ['configure', 'terminal', 'def ', 'class ', 'import']):
                score *= 1.05
            
            if score > best_score:
                best_score = score
                best_segment = segment
                best_start = i
    
    # If we found a decent match, try to refine it
    if best_score > 0.4 and best_start != -1:
        # Look for exact line matches around the best segment
        exact_matches = []
        for target_line in target_lines:
            target_norm = normalize_text_for_comparison(target_line)
            for j, page_line in enumerate(page_lines[max(0, best_start-5):best_start+window_size]):
                page_norm = normalize_text_for_comparison(page_line)
                if fuzzy_match_similarity(target_norm, page_norm) > 0.8:
                    actual_index = max(0, best_start-5) + j
                    exact_matches.append((actual_index, page_lines[actual_index]))
                    break
        
        if exact_matches:
            # Build segment from exact matches
            exact_matches.sort(key=lambda x: x[0])  # Sort by line index
            start_idx = exact_matches[0][0]
            end_idx = exact_matches[-1][0] + 1
            
            refined_segment = '\n'.join(page_lines[start_idx:end_idx])
            return refined_segment
    
    return best_segment if best_score > 0.3 else None


def find_code_in_markdown(markdown_content: str, cleaned_code: str, 
                         context_lines: int = 3) -> Tuple[Optional[str], int, int]:
    """
    Find the cleaned code block in markdown content.
    
    Args:
        markdown_content: Full markdown file content
        cleaned_code: The cleaned/formatted code to search for
        context_lines: Number of context lines to include
        
    Returns:
        Tuple of (found_text_with_context, start_line, end_line)
    """
    # Remove markdown code block markers from cleaned code
    code_content = cleaned_code.strip()
    if code_content.startswith('```'):
        lines = code_content.split('\n')
        if lines[0].startswith('```') and lines[-1].strip() == '```':
            code_content = '\n'.join(lines[1:-1])
        elif lines[0].startswith('```'):
            code_content = '\n'.join(lines[1:])
    
    markdown_lines = markdown_content.split('\n')
    code_lines = code_content.split('\n')
    
    # Search for the code sequence in markdown
    best_match_start = -1
    best_match_score = 0
    
    for i in range(len(markdown_lines) - len(code_lines) + 1):
        # Check if this segment matches our code
        segment_lines = markdown_lines[i:i + len(code_lines)]
        
        # Calculate similarity
        total_score = 0
        for j, code_line in enumerate(code_lines):
            if j < len(segment_lines):
                markdown_line = segment_lines[j].strip()
                code_line_clean = code_line.strip()
                
                # Normalize for comparison
                md_norm = normalize_text_for_comparison(markdown_line)
                code_norm = normalize_text_for_comparison(code_line_clean)
                
                line_score = fuzzy_match_similarity(md_norm, code_norm)
                total_score += line_score
        
        avg_score = total_score / len(code_lines) if code_lines else 0
        
        if avg_score > best_match_score and avg_score > 0.7:  # High threshold for accuracy
            best_match_score = avg_score
            best_match_start = i
    
    if best_match_start == -1:
        # Fallback: Multiple strategies for different document formats
        
        # Strategy 1: Flattened matching for multi-line code that appears as single line in markdown
        flattened_code = ' '.join(line.strip() for line in code_lines if line.strip())
        flattened_norm = normalize_text_for_comparison(flattened_code)
        
        best_single_line = -1
        best_single_similarity = 0
        
        for i, markdown_line in enumerate(markdown_lines):
            markdown_norm = normalize_text_for_comparison(markdown_line.strip())
            similarity = fuzzy_match_similarity(flattened_norm, markdown_norm)
            
            if similarity > best_single_similarity and similarity > 0.75:  # Flexible threshold
                best_single_similarity = similarity
                best_single_line = i
        
        if best_single_line != -1 and best_single_similarity > 0.75:
            # Found flattened match
            start_line = max(0, best_single_line - context_lines)
            end_line = min(len(markdown_lines), best_single_line + 1 + context_lines)
            context_text = '\n'.join(markdown_lines[start_line:end_line])
            return context_text, start_line + 1, end_line
        
        # Strategy 2: Adaptive partial matching - extract meaningful content words
        if len(code_lines) > 0:
            # Use all non-empty lines for keyword extraction, not just first line
            all_code_text = ' '.join(line.strip() for line in code_lines if line.strip())
            
            # Extract meaningful words (adaptive to different languages and domains)
            key_words = []
            words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_-]*\b', all_code_text.lower())
            
            for word in words:
                # Filter out very common words and too short words
                if (len(word) >= 3 and 
                    word not in ['the', 'and', 'for', 'with', 'from', 'this', 'that', 'will', 'can', 'has', 'had', 'was', 'were', 'are', 'you', 'your', 'may', 'use', 'using'] and
                    not word.isdigit()):
                    key_words.append(word)
            
            # Keep only unique words and limit to most important ones
            key_words = list(dict.fromkeys(key_words))[:10]  # Top 10 unique words
            
            if key_words:
                best_partial_line = -1
                best_partial_score = 0
                
                for i, markdown_line in enumerate(markdown_lines):
                    line_norm = normalize_text_for_comparison(markdown_line)
                    
                    # Count how many key words appear in this line
                    word_matches = sum(1 for word in key_words if word in line_norm)
                    word_score = word_matches / len(key_words)
                    
                    # Also check overall similarity with first code line
                    first_code_line_norm = normalize_text_for_comparison(code_lines[0]) if code_lines else ""
                    line_similarity = fuzzy_match_similarity(first_code_line_norm, line_norm)
                    
                    # Combined score
                    combined_score = (word_score * 0.6) + (line_similarity * 0.4)
                    
                    if combined_score > best_partial_score and combined_score > 0.5:
                        best_partial_score = combined_score
                        best_partial_line = i
                
                if best_partial_line != -1:
                    # Found partial match
                    start_line = max(0, best_partial_line - context_lines)
                    end_line = min(len(markdown_lines), best_partial_line + 1 + context_lines)
                    context_text = '\n'.join(markdown_lines[start_line:end_line])
                    return context_text, start_line + 1, end_line
        
        return None, -1, -1
    
    # Extract the text with context
    start_line = max(0, best_match_start - context_lines)
    end_line = min(len(markdown_lines), best_match_start + len(code_lines) + context_lines)
    
    context_text = '\n'.join(markdown_lines[start_line:end_line])
    
    return context_text, start_line, end_line


def replace_cleaned_with_original_code(markdown_path: str, pdf_path: str, json_file_path: str) -> Dict[str, Any]:
    """
    Replace cleaned code in markdown with original PDF code.
    
    Args:
        markdown_path: Path to the markdown file
        pdf_path: Path to the PDF file
        json_file_path: Path to the JSON file with extracted elements
        
    Returns:
        Dictionary with replacement results and statistics
    """
    results = {
        'total_code_blocks': 0,
        'successful_replacements': 0,
        'failed_replacements': 0,
        'replacement_details': []
    }
    
    try:
        # Read the original content
        with open(markdown_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        # Get all code blocks from JSON
        code_blocks = find_code_blocks(json_file_path)
        results['total_code_blocks'] = len(code_blocks)
        
        modified_content = original_content
        processed_locations = set()  # Track processed markdown locations to avoid duplicates
        
        # Process each code block
        for i, code_block in enumerate(code_blocks):
            print(f"\n🔄 Processing code block {i+1}/{len(code_blocks)}...")
            
            raw_text = code_block.get('text', '')
            cleaned_code = clean_and_format_code(raw_text)
            
            # Extract original PDF code
            original_pdf_code = extract_original_pdf_code(pdf_path, code_block)
            
            if not original_pdf_code:
                print(f"❌ Could not extract original code for block {i+1}")
                results['failed_replacements'] += 1
                continue
            
            # Find the cleaned code in markdown
            found_text, start_line, end_line = find_code_in_markdown(modified_content, cleaned_code)
            
            if found_text is None:
                print(f"❌ Could not find cleaned code in markdown for block {i+1}")
                results['failed_replacements'] += 1
                continue
            
            # Check if this location has already been processed (avoid duplicates)
            location_key = f"{start_line}-{end_line}"
            if location_key in processed_locations:
                print(f"❌ Location {location_key} already processed, skipping block {i+1}")
                results['failed_replacements'] += 1
                continue
            
            processed_locations.add(location_key)
            
            # Extract just the code part (without context)
            content_lines = modified_content.split('\n')
            
            # Find the exact code lines to replace
            code_content = cleaned_code.strip()
            if code_content.startswith('```'):
                lines = code_content.split('\n')
                if lines[0].startswith('```') and lines[-1].strip() == '```':
                    code_content = '\n'.join(lines[1:-1])
                elif lines[0].startswith('```'):
                    code_content = '\n'.join(lines[1:])
            
            # Replace the cleaned code with original PDF code
            old_text = found_text
            
            # Rebuild the replacement text with original PDF code
            context_before_lines = []
            context_after_lines = []
            code_start_in_context = -1
            code_end_in_context = -1
            
            found_lines = found_text.split('\n')
            code_lines = code_content.split('\n')
            
            # Find where the code starts within the context using flexible similarity matching
            best_segment_score = 0
            best_segment_start = -1
            best_segment_end = -1
            
            # Try different segment lengths around the expected code lines
            for segment_len in [len(code_lines), len(code_lines) + 1, len(code_lines) - 1]:
                if segment_len <= 0:
                    continue
                    
                for j in range(len(found_lines) - segment_len + 1):
                    segment = found_lines[j:j + segment_len]
                    
                    # Calculate similarity score for this segment
                    total_similarity = 0
                    comparisons = 0
                    
                    for k in range(min(len(segment), len(code_lines))):
                        if k < len(segment) and k < len(code_lines):
                            seg_norm = normalize_text_for_comparison(segment[k])
                            code_norm = normalize_text_for_comparison(code_lines[k])
                            similarity = fuzzy_match_similarity(seg_norm, code_norm)
                            total_similarity += similarity
                            comparisons += 1
                    
                    avg_similarity = total_similarity / max(1, comparisons)
                    
                    # If this segment is better than our current best
                    if avg_similarity > best_segment_score and avg_similarity > 0.7:
                        best_segment_score = avg_similarity
                        best_segment_start = j
                        best_segment_end = j + segment_len
            
            # Use the best segment we found
            if best_segment_start != -1:
                code_start_in_context = best_segment_start
                code_end_in_context = best_segment_end
            
            if code_start_in_context != -1:
                context_before_lines = found_lines[:code_start_in_context]
                context_after_lines = found_lines[code_end_in_context:]
                
                # Wrap original PDF code in triple backticks for markdown rendering
                wrapped_pdf_code = f"```\n{original_pdf_code}\n```"
                
                # Build new text with wrapped original PDF code
                new_text = '\n'.join(context_before_lines + [wrapped_pdf_code] + context_after_lines)
            else:
                # Fallback for flattened content or complex matching: find best matching lines/segments
                flattened_code_content = ' '.join(line.strip() for line in code_content.split('\n') if line.strip())
                flattened_norm = normalize_text_for_comparison(flattened_code_content)
                
                # Strategy 1: Try to find single line that matches flattened content
                best_line_match = -1
                best_line_similarity = 0
                
                for j, found_line in enumerate(found_lines):
                    found_norm = normalize_text_for_comparison(found_line.strip())
                    similarity = fuzzy_match_similarity(flattened_norm, found_norm)
                    
                    if similarity > best_line_similarity and similarity > 0.7:
                        best_line_similarity = similarity
                        best_line_match = j
                
                if best_line_match != -1:
                    # Found a good single line match
                    context_before_lines = found_lines[:best_line_match]
                    context_after_lines = found_lines[best_line_match+1:]
                    
                    # Wrap original PDF code in triple backticks for markdown rendering
                    wrapped_pdf_code = f"```\n{original_pdf_code}\n```"
                    
                    # Build new text with wrapped original PDF code
                    new_text = '\n'.join(context_before_lines + [wrapped_pdf_code] + context_after_lines)
                    code_start_in_context = best_line_match  # Mark as found for the success path
                else:
                    # Strategy 2: Look for code blocks (lines starting with ``` or containing code-like patterns)
                    for j, found_line in enumerate(found_lines):
                        line_lower = found_line.lower().strip()
                        
                        # Generic code block indicators
                        is_code_block = (
                            found_line.strip().startswith('```') or
                            # Technical command patterns
                            any(pattern in line_lower for pattern in [
                                'command', 'config', 'install', 'download', 'execute', 'run',
                                'script', 'function', 'class', 'def ', 'var ', 'const ', 'let ',
                                'import ', 'from ', 'include', '#include', 'using namespace',
                                'public ', 'private ', 'protected ', 'static ', 'final ',
                                'begin', 'end', 'start', 'stop', 'enable', 'disable'
                            ]) or
                            # Programming language indicators
                            any(lang in line_lower for lang in [
                                'python', 'java', 'javascript', 'c++', 'c#', 'ruby', 'php',
                                'sql', 'html', 'css', 'bash', 'shell', 'powershell', 'cmd'
                            ]) or
                            # Special characters often in code
                            len([c for c in found_line if c in '(){}[]<>=;:']) >= 3 or
                            # Lines with many technical terms (contains numbers, dots, dashes)
                            bool(re.search(r'[a-zA-Z]+[-_\.][a-zA-Z0-9]', found_line))
                        )
                        
                        if is_code_block:
                            # Check if next few lines contain similar content
                            segment_text = ' '.join(found_lines[j:j+3]).strip()
                            segment_norm = normalize_text_for_comparison(segment_text)
                            similarity = fuzzy_match_similarity(flattened_norm, segment_norm)
                            
                            if similarity > 0.5:  # Lower threshold for flexible matching
                                # Found a potential code block
                                # Find the end of the code block (next ``` or empty line)
                                code_block_end = j + 1
                                for k in range(j + 1, len(found_lines)):
                                    if found_lines[k].strip() == '```' or found_lines[k].strip() == '':
                                        code_block_end = k + 1
                                        break
                                
                                context_before_lines = found_lines[:j]
                                context_after_lines = found_lines[code_block_end:]
                                
                                # Wrap original PDF code in triple backticks for markdown rendering
                                wrapped_pdf_code = f"```\n{original_pdf_code}\n```"
                                
                                # Build new text with wrapped original PDF code
                                new_text = '\n'.join(context_before_lines + [wrapped_pdf_code] + context_after_lines)
                                code_start_in_context = j  # Mark as found for the success path
                                break
            
            # Check if we found boundaries (either through direct matching or flattened fallback)
            if code_start_in_context != -1:
                # Replace in content
                modified_content = modified_content.replace(old_text, new_text, 1)
                
                results['successful_replacements'] += 1
                results['replacement_details'].append({
                    'block_number': i + 1,
                    'page': code_block.get('page_number'),
                    'original_length': len(raw_text),
                    'pdf_length': len(original_pdf_code),
                    'cleaned_length': len(cleaned_code)
                })
                
                print(f"✅ Successfully replaced code block {i+1}")
                print(f"   Original PDF: {original_pdf_code[:50]}...")
                print(f"   Replaced in markdown")
            else:
                print(f"❌ Could not locate exact code boundaries for block {i+1}")
                results['failed_replacements'] += 1
        
        # Write the modified content back to the file
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)
        
        print(f"\n🎉 Replacement completed!")
        print(f"   Total code blocks: {results['total_code_blocks']}")
        print(f"   Successful: {results['successful_replacements']}")
        print(f"   Failed: {results['failed_replacements']}")
        
    except Exception as e:
        print(f"❌ Error during replacement: {e}")
        results['error'] = str(e)
    
    return results
