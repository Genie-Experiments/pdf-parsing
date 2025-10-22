import json
import re
from difflib import SequenceMatcher
from typing import List, Tuple, Optional
import logging
from datetime import datetime
import os
import sys
from pathlib import Path

# Add utils directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'utils'))
from get_markdown_file_path import get_markdown_file_path

class OCRErrorFixer:
    def __init__(self, json_path: str, extracted_text_path: str, markdown_path: str):
        """
        Initialize the OCR Error Fixer
        
        Args:
            json_path: Path to the JSON file with OCR errors
            extracted_text_path: Path to the accurate extracted text file
            markdown_path: Path to the markdown file to fix
        """
        self.json_path = json_path
        self.extracted_text_path = extracted_text_path
        self.markdown_path = markdown_path
        
        # Load data
        with open(json_path, 'r', encoding='utf-8') as f:
            self.json_data = json.load(f)
        
        with open(extracted_text_path, 'r', encoding='utf-8') as f:
            self.accurate_text = f.read()
        
        with open(markdown_path, 'r', encoding='utf-8') as f:
            self.markdown_content = f.read()
    
    def is_table_of_contents(self, text: str) -> bool:
        """
        Heuristics to detect table of contents entries
        """
        # Check for page numbers at the end
        if re.search(r'\d+\s*$', text.strip()):
            return True
        
        # Check for common TOC patterns
        toc_patterns = [
            r'^Table of Contents',
            r'\.{3,}',  # Multiple dots (leader dots)
            r'on page \d+',
            r'see page \d+',
        ]
        
        for pattern in toc_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def split_text_by_lines(self, text: str) -> List[str]:
        """
        Split text by various line separators and filter out empty lines
        
        Handles multiple line separator types:
        - \n (standard newlines)
        - \r\n (Windows newlines)
        - -\n (hyphenated line breaks)
        - • (bullet points)
        - numbered lists (1., 2., etc.)
        - lettered lists (a., b., etc.)
        - ◦ (hollow bullet)
        - ▪ (square bullet)
        - ○ (circle bullet)
        - – (en dash as separator)
        - — (em dash as separator)
        """
        # First, normalize the text by handling special cases
        text = text.replace('\r\n', '\n')  # Normalize Windows newlines
        
        # Define separator patterns
        separators = [
            r'\n',                          # Standard newline
            r'•\s*',                        # Bullet point
            r'◦\s*',                        # Hollow bullet
            r'▪\s*',                        # Square bullet
            r'○\s*',                        # Circle bullet
            r'►\s*',                        # Arrow bullet
            r'✓\s*',                        # Checkmark
            r'−\s*',                        # Minus as bullet
            r'–\s*(?=[A-Z])',              # En dash before capital letter
            r'—\s*(?=[A-Z])',              # Em dash before capital letter
            r'\d+\.\s+',                    # Numbered list (1. 2. etc.)
            r'[a-z]\.\s+',                  # Lettered list (a. b. etc.)
            r'[A-Z]\.\s+',                  # Capital lettered list (A. B. etc.)
            r'[ivxlcdm]+\.\s+',            # Roman numerals (i. ii. etc.)
            r'[IVXLCDM]+\.\s+',            # Capital Roman numerals (I. II. etc.)
            r'\([a-z]\)\s*',               # Parenthetical letters (a) (b) etc.)
            r'\(\d+\)\s*',                 # Parenthetical numbers (1) (2) etc.)
        ]
        
        # Create a combined pattern
        combined_pattern = '|'.join(f'(?:{sep})' for sep in separators)
        
        # Handle hyphenated line breaks specially
        # Replace -\n with empty string to join hyphenated words
        text = re.sub(r'-\s*\n\s*', '', text)
        
        # Split by the combined pattern
        lines = re.split(combined_pattern, text)
        
        # Clean up the lines
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            
            # Remove leading/trailing special characters that might remain
            line = re.sub(r'^[•◦▪○►✓−–—]\s*', '', line)
            line = re.sub(r'^[\d+\.\)]+\s*', '', line)
            line = re.sub(r'^\([a-zA-Z0-9]+\)\s*', '', line)
            
            # Only keep non-empty lines with substantial content
            if line and len(line) > 1:
                cleaned_lines.append(line)
        
        return cleaned_lines
    
    def fuzzy_match(self, ocr_text: str, accurate_text: str, threshold: float = 0.6) -> Optional[Tuple[str, float]]:
        """
        Find the best fuzzy match for ocr_text in accurate_text
        
        Args:
            ocr_text: Text with potential OCR errors
            accurate_text: The accurate text to search in
            threshold: Minimum similarity ratio (0-1)
        
        Returns:
            Tuple of (matched_text, similarity_score) or None
        """
        ocr_text_clean = ocr_text.strip()
        if len(ocr_text_clean) < 5:  # Skip very short texts
            return None
        
        # Optimized fuzzy matching: split accurate text into lines and check each line
        best_match = None
        best_ratio = 0
        
        lines = accurate_text.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines and very short lines
            if len(line) < 3:
                continue
                
            # Quick length filter - only check lines with similar length
            length_ratio = min(len(ocr_text_clean), len(line)) / max(len(ocr_text_clean), len(line))
            if length_ratio < 0.3:  # Skip lines that are too different in length
                continue
            
            # Calculate similarity
            ratio = SequenceMatcher(None, ocr_text_clean.lower(), line.lower()).ratio()
            
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = line
        
        if best_ratio >= threshold:
            # If the match starts with "Text: ", extract just the content part
            if best_match and best_match.startswith("Text: "):
                best_match = best_match[6:]  # Remove "Text: " prefix
            
            # CRITICAL FIX: Never replace with shorter text unless it's clearly better
            # This prevents replacing correct words with fragments
            if len(best_match) < len(ocr_text_clean) * 0.8:  # If replacement is significantly shorter
                # Only allow if similarity is very high (> 0.95) indicating it's likely a correction
                # of extra characters, not a replacement with a fragment
                if best_ratio < 0.95:
                    return None
            
            return (best_match, best_ratio)
        
        return None
    
    def extract_texts_from_json(self) -> List[Tuple[str, dict]]:
        """
        Extract all text elements from JSON (excluding code, tables, and TOC)
        Returns list of tuples: (text, metadata)
        """
        texts_to_fix = []
        
        for page in self.json_data.get('pages', []):
            page_num = page.get('page_number')
            
            for element in page.get('elements', []):
                label = element.get('label', '')
                text = element.get('text', '')
                
                # Skip code blocks and tables
                if label in ['code', 'tab']:
                    continue
                
                # Skip table of contents
                if self.is_table_of_contents(text):
                    continue
                
                # Skip empty text
                if not text.strip():
                    continue
                
                # Split by various line separators
                lines = self.split_text_by_lines(text)
                
                for line in lines:
                    if len(line) > 3:  # Skip very short lines
                        texts_to_fix.append((line, {
                            'page': page_num,
                            'label': label,
                            'original_text': text
                        }))
        
        return texts_to_fix
    
    def fix_markdown(self, output_path: str, min_similarity: float = 0.65):
        """
        Fix OCR errors in markdown using accurate text
        
        Args:
            output_path: Path to save the corrected markdown
            min_similarity: Minimum similarity threshold for replacements
        """
        texts_to_fix = self.extract_texts_from_json()
        
        corrected_markdown = self.markdown_content
        replacements = []
        
        print(f"Processing {len(texts_to_fix)} text segments...")
        
        for idx, (ocr_text, metadata) in enumerate(texts_to_fix):
            if idx % 100 == 0:
                print(f"Progress: {idx}/{len(texts_to_fix)}")
            
            # Find the accurate version
            match_result = self.fuzzy_match(ocr_text, self.accurate_text, threshold=min_similarity)
            
            if match_result:
                accurate_version, similarity = match_result
                
                # Only replace if there's actually a difference
                if ocr_text != accurate_version:
                    # CRITICAL VALIDATION: Additional checks to prevent bad replacements
                    
                    # 0. FUNDAMENTAL CHECK: Be very strict about replacements that make text shorter
                    # unless similarity is very high
                    if len(accurate_version) < len(ocr_text):
                        length_ratio = len(accurate_version) / len(ocr_text)
                        required_similarity = 0.85 + (0.15 * (1 - length_ratio))  # Higher threshold for shorter replacements
                        if similarity < required_similarity:
                            continue
                    
                    # 1. Don't replace if the "correction" looks like a fragment
                    if len(accurate_version.strip()) < 3:
                        continue
                    
                    # 2. Don't replace if the "correction" looks like malformed text or OCR artifacts
                    if (accurate_version.endswith(('.', 'a.', 'ing.', 'ed.', 's.')) or
                        accurate_version.endswith(('a', 'inga', 'eda', 'sa')) or  # Common OCR artifacts
                        accurate_version.endswith(('s')) and len(accurate_version) == 4 or  # Like "Thes"
                        (len(accurate_version) > 3 and accurate_version.endswith('s') and 
                         not accurate_version.endswith(('ness', 'less', 'ous', 'ions', 'ings', 'ates', 'ures', 'ants', 'ents')))):
                        continue
                    
                    # Check for common OCR artifacts where text gets extra characters
                    if len(accurate_version) > len(ocr_text) and similarity < 0.9:
                        # If replacement is longer but similarity is not very high, it might be adding artifacts
                        if any(accurate_version.endswith(suffix) for suffix in ['a', 'inga', 's']):
                            # Check if removing the suffix gives us the original
                            for suffix in ['a', 'inga', 's']:
                                if accurate_version.endswith(suffix):
                                    without_suffix = accurate_version[:-len(suffix)]
                                    if without_suffix == ocr_text or without_suffix in ocr_text:
                                        continue  # Skip this replacement as it's adding artifacts
                    
                    # 3. Don't replace complete words with partial words or fragments
                    ocr_words = ocr_text.split()
                    accurate_words = accurate_version.split()
                    
                    # Stricter validation for word-level replacements
                    if len(ocr_words) > 0 and len(accurate_words) > 0:
                        # If replacement has fewer words, require very high similarity
                        if len(accurate_words) < len(ocr_words) and similarity < 0.95:
                            continue
                        
                        # Don't replace if the "correction" looks like a substring or fragment
                        # Don't replace if any word in the replacement is suspiciously short or malformed
                        suspicious_replacement = False
                        for word in accurate_words:
                            if len(word) <= 2 and len(ocr_text) > 5:  # Don't replace long text with 1-2 char words
                                suspicious_replacement = True
                                break
                        if suspicious_replacement:
                            continue
                        
                        # Check for malformed words (common OCR artifacts)
                        for word in accurate_words:
                            # Words that end with single letters that seem wrong
                            if (len(word) > 3 and word.endswith(('s', 'a', 'e', 'i', 'o')) and 
                                word not in ['the', 'and', 'for', 'are', 'can', 'has', 'his', 'its', 'was', 'who']):
                                # Check if this might be a truncated word by seeing if original contains a longer version
                                longer_candidate = None
                                for ocr_word in ocr_words:
                                    if ocr_word.startswith(word) and len(ocr_word) > len(word):
                                        longer_candidate = ocr_word
                                        break
                                if longer_candidate:
                                    suspicious_replacement = True
                                    break
                        if suspicious_replacement:
                            continue
                    
                    # 4. Sanity check: Don't replace if the replacement seems random
                    # Check if replacement contains mostly the same characters as original
                    ocr_chars = set(ocr_text.lower().replace(' ', ''))
                    acc_chars = set(accurate_version.lower().replace(' ', ''))
                    
                    # If replacement has very different character composition, be more careful
                    if len(ocr_text) > 3 and len(accurate_version) < len(ocr_text) * 0.7:
                        char_overlap = len(ocr_chars.intersection(acc_chars)) / max(len(ocr_chars), 1)
                        if char_overlap < 0.5:  # Less than 50% character overlap in short replacement
                            continue
                    
                    # CRITICAL FIX: Only replace if OCR text appears as complete units, not fragments
                    
                    # Check if this looks like a complete text unit vs a fragment
                    ocr_text_stripped = ocr_text.strip()
                    
                    # Strategy 1: Only replace if OCR text appears on its own line or as a complete sentence
                    lines = corrected_markdown.split('\n')
                    replacement_made = False
                    
                    for i, line in enumerate(lines):
                        # Check if the OCR text is the entire line (or most of it)
                        line_stripped = line.strip()
                        
                        # Case 1: Exact line match
                        if line_stripped == ocr_text_stripped:
                            lines[i] = line.replace(ocr_text_stripped, accurate_version)
                            replacement_made = True
                            break
                            
                        # Case 2: OCR text is at the start or end of line (complete phrase)
                        elif (line_stripped.startswith(ocr_text_stripped + ' ') or 
                              line_stripped.startswith(ocr_text_stripped + '.') or
                              line_stripped.startswith(ocr_text_stripped + ',') or
                              line_stripped.endswith(' ' + ocr_text_stripped) or
                              line_stripped.endswith('.' + ocr_text_stripped) or
                              line_stripped.endswith(',' + ocr_text_stripped)):
                            
                            # CRITICAL: Don't replace if accurate_version contains the original line
                            # This prevents duplication issues
                            if ocr_text_stripped in accurate_version and len(accurate_version) > len(ocr_text_stripped) * 2:
                                # Skip this replacement as it would likely cause duplication
                                continue
                            
                            # Only replace if the OCR text is substantial part of the line
                            if len(ocr_text_stripped) > len(line_stripped) * 0.3:
                                escaped_ocr = re.escape(ocr_text_stripped)
                                lines[i] = re.sub(escaped_ocr, accurate_version, line, count=1)
                                replacement_made = True
                                break
                    
                    # Case 3: For short OCR texts, only replace if they're complete words
                    if not replacement_made and len(ocr_text_stripped.split()) <= 3:
                        # CRITICAL: Don't replace if accurate_version contains the OCR text and is much longer
                        # This prevents duplication issues
                        if ocr_text_stripped in accurate_version and len(accurate_version) > len(ocr_text_stripped) * 2:
                            # Skip this replacement as it would likely cause duplication
                            pass
                        else:
                            # Use word boundary matching for short phrases
                            escaped_ocr = re.escape(ocr_text_stripped)
                            word_pattern = r'\b' + escaped_ocr + r'\b'
                            
                            if re.search(word_pattern, corrected_markdown):
                                # Check that we're not replacing a small part of a much larger context
                                corrected_markdown = re.sub(word_pattern, accurate_version, corrected_markdown, count=1)
                                replacement_made = True
                    
                    # Update the markdown if replacement was made
                    if replacement_made:
                        if 'lines' in locals():
                            corrected_markdown = '\n'.join(lines)
                        
                        replacements.append({
                            'page': metadata['page'],
                            'ocr_text': ocr_text,
                            'corrected_text': accurate_version,
                            'similarity': similarity
                        })
        
        # Save corrected markdown
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(corrected_markdown)
        
        # Save replacement log
        log_path = output_path.replace('.md', '_corrections.json')
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(replacements, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Corrected markdown saved to: {output_path}")
        print(f"✓ Made {len(replacements)} corrections")
        print(f"✓ Correction log saved to: {log_path}")
        
        return corrected_markdown, replacements


def fix_ocr_errors_batch(results_directory: str, raw_pdf_text_directory: str, min_similarity: float = 0.65):
    """
    Batch process OCR error fixing for all files in the results directory.
    
    Args:
        results_directory: Directory containing JSON and markdown files from processing
        raw_pdf_text_directory: Directory containing extracted raw text files
        min_similarity: Minimum similarity threshold for replacements
    """
    print("Starting batch OCR error correction...")
    print(f"Results directory: {results_directory}")
    print(f"Raw PDF text directory: {raw_pdf_text_directory}")
    print(f"Minimum similarity threshold: {min_similarity}")
    print("-" * 60)
    
    # Check if directories exist
    if not os.path.exists(results_directory):
        print(f"Error: Results directory '{results_directory}' does not exist!")
        return False
    
    if not os.path.exists(raw_pdf_text_directory):
        print(f"Error: Raw PDF text directory '{raw_pdf_text_directory}' does not exist!")
        return False
    
    # Find all JSON files in the results directory (recursively)
    json_files = []
    for root, dirs, files in os.walk(results_directory):
        for file in files:
            if file.lower().endswith('.json'):
                json_files.append(os.path.join(root, file))
    
    if not json_files:
        print(f"No JSON files found in '{results_directory}'")
        return True
    
    print(f"Found {len(json_files)} JSON files to process\n")
    
    successful_corrections = 0
    failed_corrections = 0
    skipped_corrections = 0
    
    for i, json_path in enumerate(json_files, 1):
        try:
            # Get relative path from results directory for display
            rel_json_path = os.path.relpath(json_path, results_directory)
            print(f"[{i}/{len(json_files)}] Processing: {rel_json_path}")
            
            # Determine the corresponding markdown and text file paths
            base_name = os.path.splitext(os.path.basename(json_path))[0]
            
            # Use utility function to get markdown file path
            markdown_path = str(get_markdown_file_path(json_path))
            
            # Get the parent directory of the JSON file for relative path calculation
            json_dir = os.path.dirname(json_path)
            
            # For text files, we need to map back to the original PDF structure
            # The JSON path structure is: results_directory/folder/file/recognition_json/file.json
            # The text path structure should be: raw_pdf_text_directory/folder/file.txt
            
            # Get the path components
            json_path_obj = Path(json_path)
            
            # Navigate up from recognition_json to get the parent directory
            parent_of_recognition = json_path_obj.parent.parent
            
            # Get the relative path from results directory to this parent
            rel_path_to_parent = os.path.relpath(parent_of_recognition, results_directory)
            
            # Construct the text file path
            if rel_path_to_parent == '.':
                text_path = os.path.join(raw_pdf_text_directory, base_name + '.txt')
            else:
                text_path = os.path.join(raw_pdf_text_directory, rel_path_to_parent, base_name + '.txt')
            
            # Check if required files exist
            if not os.path.exists(markdown_path):
                print(f"  → Skipping (markdown file not found): {markdown_path}")
                skipped_corrections += 1
                continue
            
            if not os.path.exists(text_path):
                print(f"  → Skipping (text file not found): {text_path}")
                skipped_corrections += 1
                continue
            
            # Initialize OCR fixer and process
            fixer = OCRErrorFixer(json_path, text_path, markdown_path)
            
            # Generate output path for corrected markdown (in the same directory as original markdown)
            markdown_dir = os.path.dirname(markdown_path)
            output_path = os.path.join(markdown_dir, base_name + '_corrected.md')
            
            # Fix OCR errors
            corrected_md, replacements = fixer.fix_markdown(output_path, min_similarity)
            
            successful_corrections += 1
            print(f"  → Fixed {len(replacements)} errors, saved to: {os.path.basename(output_path)}")
            
        except Exception as e:
            failed_corrections += 1
            print(f"  → Error processing {rel_json_path}: {str(e)}")
        
        print()  # Empty line for readability
    
    # Print summary
    print("=" * 60)
    print("OCR Error Correction Summary:")
    print(f"Total JSON files found: {len(json_files)}")
    print(f"Successfully processed: {successful_corrections}")
    print(f"Skipped files: {skipped_corrections}")
    print(f"Failed corrections: {failed_corrections}")
    
    return failed_corrections == 0


# Example usage
if __name__ == "__main__":
    # If run directly, import config and use default settings
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))
    from config import OUTPUT_DIRECTORY, RAW_PDF_TEXT_DIR
    
    # Run batch processing with default directories
    success = fix_ocr_errors_batch(OUTPUT_DIRECTORY, RAW_PDF_TEXT_DIR, min_similarity=0.75)
    
    if success:
        print("\n✅ OCR error correction completed successfully!")
    else:
        print("\n❌ OCR error correction failed!")
    
    sys.exit(0 if success else 1)