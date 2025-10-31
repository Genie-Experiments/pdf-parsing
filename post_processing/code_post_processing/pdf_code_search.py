import json
import re
from typing import List, Dict, Any, Tuple, Optional
from difflib import SequenceMatcher
from dataclasses import dataclass
import fitz  # PyMuPDF - Required dependency
from utils.logger import get_logger, log_success, log_error, log_warning


@dataclass
class CodeMatch:
    """Represents a match between cleaned code and PDF content."""
    page_number: int
    confidence_score: float
    pdf_text: str
    context_text: str
    json_element: Dict[str, Any]
    bbox: List[float]  # Bounding box in PDF coordinates


def detect_content_type(text: str) -> str:
    """
    Detect the type of content to apply appropriate matching strategies.
    
    Returns:
        'code', 'command', 'config', 'natural_language', or 'mixed'
    """
    if not text or len(text.strip()) < 3:
        return 'mixed'
    
    text_sample = text[:500].lower()  # Sample for analysis
    
    # Programming language patterns
    code_indicators = [
        r'\bdef\s+\w+\(',  # Python functions
        r'\bclass\s+\w+',  # Class definitions
        r'\bimport\s+\w+', r'\bfrom\s+\w+\s+import',  # Python imports
        r'\b(int|str|bool|float|void|char|public|private|static)\b',  # Type keywords
        r'[{}();]',        # Common code punctuation
        r'\b(if|else|for|while|return|function|var|let|const)\b',  # Control flow
        r'=\s*[\[{]',      # Assignment to structures
        r'\w+\.\w+',       # Method calls
    ]
    
    command_indicators = [
        r'^\s*[a-z-]+\s+--?\w+',  # CLI commands with flags
        r'^\s*(sudo|cd|ls|cp|mv|rm|mkdir|chmod|chown)\b',  # Unix commands
        r'^\s*(git|npm|pip|docker|kubectl)\b',  # Common tools
        r'\s-[a-zA-Z]\b',  # Short flags
        r'\s--\w+',        # Long flags
    ]
    
    config_indicators = [
        r'^\s*\w+\s*[=:]\s*\w+',  # Key-value pairs with values
        r'\w+\s*=\s*\w+',         # Assignment patterns
        r'^\s*\[.*\]',            # Section headers
        r'^\s*#.*',               # Comments
        r'\{[^}]*:',              # JSON-like structure
        r'\w+\.\w+\s*=',          # Property assignments (like server.port)
        r':\s*\d+',               # Port numbers and numeric configs
    ]
    
    # Count matches
    code_score = sum(1 for pattern in code_indicators if re.search(pattern, text_sample))
    command_score = sum(1 for pattern in command_indicators if re.search(pattern, text_sample))
    config_score = sum(1 for pattern in config_indicators if re.search(pattern, text_sample))
    
    # Determine content type
    scores = {'code': code_score, 'command': command_score, 'config': config_score}
    max_type = max(scores, key=scores.get)
    
    # Get logger for debugging (only if text is substantial for debugging)
    if len(text) > 50:  # Only log for substantial content
        logger = get_logger(__name__)
        logger.debug("Content type detection - scores: code=%d, command=%d, config=%d → %s", 
                    code_score, command_score, config_score, max_type if scores[max_type] >= 2 else 'mixed/natural')
    
    if scores[max_type] >= 2:
        return max_type
    elif any(score > 0 for score in scores.values()):
        return 'mixed'
    else:
        return 'natural_language'


def fuzzy_match_similarity(text1: str, text2: str, adaptive: bool = True) -> float:
    """
    Calculate similarity between two text strings with adaptive normalization.
    
    Args:
        text1, text2: Texts to compare
        adaptive: If True, applies content-aware normalization
        
    Returns:
        Score between 0.0 (no match) and 1.0 (perfect match)
    """
    if not text1 or not text2:
        return 0.0
    
    # Detect content type for adaptive processing
    content_type = detect_content_type(text1) if adaptive else 'mixed'
    
    # Choose normalization strategy based on content
    aggressive_mode = content_type in ['code', 'command', 'config']
    
    # Normalize texts for comparison
    norm1 = normalize_text_for_comparison(text1, aggressive_mode)
    norm2 = normalize_text_for_comparison(text2, aggressive_mode)
    
    if not norm1 or not norm2:
        return 0.0
    
    similarity = SequenceMatcher(None, norm1, norm2).ratio()
    
    # Apply content-type specific adjustments
    if content_type == 'natural_language' and similarity < 0.7:
        # For natural language, also try word-based comparison
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        if words1 and words2:
            word_similarity = len(words1 & words2) / len(words1 | words2)
            similarity = max(similarity, word_similarity * 0.8)  # Slight penalty for word-only match
    
    return similarity


def normalize_text_for_comparison(text: str, aggressive_mode: bool = False) -> str:
    """
    Normalize text for fuzzy matching with adaptive strategies:
    - Converting to lowercase
    - Removing extra whitespace
    - Normalizing common OCR errors and unicode issues
    - Handling different document types and languages
    
    Args:
        text: Text to normalize
        aggressive_mode: If True, applies more aggressive normalization for difficult matches
    """
    if not text:
        return ""
    
    # Convert to lowercase and strip
    text = text.lower().strip()
    
    # Unicode and typography corrections (common across all document types)
    unicode_corrections = {
        'ﬁ': 'fi',  'ﬂ': 'fl',  'ﬀ': 'ff',  'ﬃ': 'ffi',  'ﬄ': 'ffl',  # ligatures
        '"': '"',   '"': '"',   ''': "'",   ''': "'",                    # smart quotes
        '–': '-',   '—': '-',   '−': '-',                                # dashes
        '…': '...',  '․': '.',  '‥': '..',                              # dots/ellipsis
        '\xa0': ' ', '\u2000': ' ', '\u2001': ' ', '\u2002': ' ',       # spaces
        '\u2003': ' ', '\u2004': ' ', '\u2005': ' ', '\u2006': ' ',     # more spaces
        '\u2007': ' ', '\u2008': ' ', '\u2009': ' ', '\u200a': ' ',     # more spaces
        '\u3000': ' ',  # ideographic space
        '°': 'deg',     # degree symbol often confused
        '×': 'x',       # multiplication sign vs x
        '÷': '/',       # division sign
    }
    
    for bad, good in unicode_corrections.items():
        text = text.replace(bad, good)
    
    # Basic OCR character corrections (conservative for general use)
    if aggressive_mode:
        # More aggressive corrections for difficult documents
        ocr_corrections = {
            'rn': 'm',   'ii': 'll',  'vv': 'w',   'cl': 'd',
            'ri': 'n',   'ni': 'n',   'ln': 'h',   'hl': 'h',
            'I': '1',    'l': '1',    'O': '0',    'o': '0',
            'S': '5',    's': '5',    'G': '6',    'g': '9',
            'B': '8',    'Z': '2',    'i': '1',
        }
        for bad, good in ocr_corrections.items():
            text = text.replace(bad, good)
    
    # Remove extra whitespace and normalize
    text = re.sub(r'\s+', ' ', text)
    
    # Keep important punctuation for code/technical content but remove noise
    # Preserve: letters, numbers, common symbols, underscores, hyphens
    if aggressive_mode:
        # More aggressive punctuation removal
        text = re.sub(r'[^\w\s\-_]', ' ', text)
    else:
        # Conservative: keep common technical symbols
        text = re.sub(r'[^\w\s\-_.,;:()\[\]{}="\'<>/\\@#$%&*+|~`^?!]', ' ', text)
    
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def get_context_elements(json_data: Dict[str, Any], code_element: Dict[str, Any], 
                        context_window: int = 3) -> List[Dict[str, Any]]:
    """
    Get context elements (paragraphs, headers, etc.) that appear before/around a code element.
    
    Args:
        json_data: Full JSON data from the document
        code_element: The code element we're looking for context around
        context_window: Number of elements before/after to include
        
    Returns:
        List of context elements with their text content
    """
    target_page = None
    target_reading_order = code_element.get('reading_order')
    
    # Find the page containing this code element
    for page in json_data.get('pages', []):
        for element in page.get('elements', []):
            if (element.get('reading_order') == target_reading_order and 
                element.get('label') == 'code'):
                target_page = page
                break
        if target_page:
            break
    
    if not target_page:
        return []
    
    # Get elements from the same page, sorted by reading order
    page_elements = sorted(
        target_page.get('elements', []), 
        key=lambda x: x.get('reading_order', 0)
    )
    
    # Find the index of our code element
    code_index = -1
    for i, element in enumerate(page_elements):
        if (element.get('reading_order') == target_reading_order and 
            element.get('label') == 'code'):
            code_index = i
            break
    
    if code_index == -1:
        return []
    
    # Get context elements (prioritize elements before the code)
    context_elements = []
    
    # Elements before (more important for context)
    start_idx = max(0, code_index - context_window)
    for i in range(start_idx, code_index):
        element = page_elements[i]
        if element.get('label') in ['para', 'header', 'title', 'list']:
            context_elements.append(element)
    
    # Elements after (less important)
    end_idx = min(len(page_elements), code_index + context_window + 1)
    for i in range(code_index + 1, end_idx):
        element = page_elements[i]
        if element.get('label') in ['para', 'header', 'title']:
            context_elements.append(element)
    
    return context_elements


def search_code_in_pdf(pdf_path: str, json_file_path: str, cleaned_code: str, 
                      json_element: Dict[str, Any], min_confidence: float = None) -> List[CodeMatch]:
    """
    Search for cleaned code in the actual PDF file using fuzzy matching with context.
    
    Args:
        pdf_path: Path to the PDF file
        json_file_path: Path to the JSON file with extracted elements
        cleaned_code: The cleaned/formatted code to search for
        json_element: The original JSON element containing the raw code
        min_confidence: Minimum confidence score (auto-determined if None)
        
    Returns:
        List of CodeMatch objects sorted by confidence score (highest first)
    """
    logger = get_logger(__name__)
    matches = []
    
    try:
        # Load JSON data for context
        with open(json_file_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        # Check if context is already provided, otherwise extract it
        if 'context_text' in json_element and json_element['context_text']:
            context_text = json_element['context_text']
            logger.debug("Using provided context: %s...", context_text[:50])
        else:
            # Get context elements around the code
            context_elements = get_context_elements(json_data, json_element)
            context_text = ' '.join(elem.get('text', '') for elem in context_elements)
            logger.debug("Extracted context: %s...", context_text[:50])
        
        # Extract cleaned code content (remove markdown formatting)
        code_content = cleaned_code.strip()
        if code_content.startswith('```'):
            lines = code_content.split('\n')
            # Remove first and last lines if they're markdown markers
            if lines[0].startswith('```') and lines[-1].strip() == '```':
                code_content = '\n'.join(lines[1:-1])
            elif lines[0].startswith('```'):
                code_content = '\n'.join(lines[1:])
        
        # Determine adaptive minimum confidence based on code content type
        if min_confidence is None:
            content_type = detect_content_type(code_content)
            adaptive_thresholds = {
                'code': 0.4,           # Programming code - higher threshold needed
                'command': 0.35,       # CLI commands - medium threshold
                'config': 0.3,         # Configuration - lower threshold (more variation)
                'natural_language': 0.5,  # Natural text - higher threshold
                'mixed': 0.35          # Mixed content - balanced threshold
            }
            min_confidence = adaptive_thresholds.get(content_type, 0.35)
            logger.debug("Auto-detected content type '%s', using confidence threshold: %.2f", 
                        content_type, min_confidence)
        else:
            logger.debug("Using provided confidence threshold: %.2f", min_confidence)
        
        # Extract text from PDF pages using PyMuPDF
        logger.info("Opening PDF file: %s", pdf_path)
        pdf_doc = fitz.open(pdf_path)
        logger.info("Searching through %d PDF pages for code matches", len(pdf_doc))
        
        # Search through PDF pages
        for page_num in range(len(pdf_doc)):
            page = pdf_doc[page_num]
            page_text = page.get_text()
            
            # Try different matching strategies
            page_matches = _match_with_strategies(
                page_text, code_content, context_text, json_element, 
                page_num + 1, min_confidence, page, detect_content_type(code_content)
            )
            matches.extend(page_matches)
            
            if page_matches:
                logger.debug("Found %d matches on page %d", len(page_matches), page_num + 1)
        
        pdf_doc.close()
        log_success(f"PDF search completed. Found {len(matches)} total matches", logger)
        
    except Exception as e:
        log_error(f"Error searching PDF: {e}", logger)
        return []
    
    # Sort matches by confidence score (highest first)
    matches.sort(key=lambda x: x.confidence_score, reverse=True)
    if matches:
        logger.info("Best match has confidence score: %.3f", matches[0].confidence_score)
    
    # Remove duplicate matches (same page, similar bbox)
    unique_matches = []
    for match in matches:
        is_duplicate = False
        for existing in unique_matches:
            if (existing.page_number == match.page_number and
                abs(existing.confidence_score - match.confidence_score) < 0.1):
                is_duplicate = True
                break
        if not is_duplicate:
            unique_matches.append(match)
    
    return unique_matches


def _match_with_strategies(page_text: str, code_content: str, context_text: str, 
                         json_element: Dict[str, Any], page_num: int, 
                         min_confidence: float, page_obj=None, content_type: str = 'mixed') -> List[CodeMatch]:
    """
    Try different matching strategies to find the code in the PDF page.
    """
    matches = []
    
    # Strategy 1: Direct fuzzy match with adaptive processing
    confidence = fuzzy_match_similarity(page_text, code_content, adaptive=True)
    if confidence >= min_confidence:
        matches.append(CodeMatch(
            page_number=page_num,
            confidence_score=confidence,
            pdf_text=page_text[:500] + "..." if len(page_text) > 500 else page_text,
            context_text=context_text,
            json_element=json_element,
            bbox=json_element.get('bbox', [])
        ))
    
    # Strategy 2: Match with context + code (if available)
    if context_text and len(context_text.strip()) > 10:
        combined_text = context_text + " " + code_content
        confidence = fuzzy_match_similarity(page_text, combined_text, adaptive=True)
        if confidence >= min_confidence * 0.85:  # Slightly lower threshold for context matches
            matches.append(CodeMatch(
                page_number=page_num,
                confidence_score=confidence * 0.9,  # Slightly lower priority
                pdf_text=page_text[:500] + "..." if len(page_text) > 500 else page_text,
                context_text=context_text,
                json_element=json_element,
                bbox=json_element.get('bbox', [])
            ))
    
    # Strategy 3: Line-by-line matching for code blocks
    code_lines = [line.strip() for line in code_content.split('\n') if line.strip()]
    if len(code_lines) > 1:
        page_lines = [line.strip() for line in page_text.split('\n') if line.strip()]
        
        # Find the best matching consecutive sequence
        best_match_score = 0
        best_match_start = -1
        
        for i in range(len(page_lines) - len(code_lines) + 1):
            page_segment = page_lines[i:i + len(code_lines)]
            total_score = 0
            
            for j, code_line in enumerate(code_lines):
                if j < len(page_segment):
                    line_score = fuzzy_match_similarity(page_segment[j], code_line)
                    total_score += line_score
                    
            avg_score = total_score / len(code_lines) if code_lines else 0
            
            if avg_score > best_match_score:
                best_match_score = avg_score
                best_match_start = i
        
        if best_match_score >= min_confidence:
            matched_text = '\n'.join(page_lines[best_match_start:best_match_start + len(code_lines)])
            matches.append(CodeMatch(
                page_number=page_num,
                confidence_score=best_match_score * 0.95,  # High priority for line matching
                pdf_text=matched_text,
                context_text=context_text,
                json_element=json_element,
                bbox=json_element.get('bbox', [])
            ))
    
    return matches


def find_all_code_matches(pdf_path: str, json_file_path: str, 
                         min_confidence: float = 0.3) -> Dict[str, List[CodeMatch]]:
    """
    Find matches for all code blocks in the JSON file.
    
    Args:
        pdf_path: Path to the PDF file
        json_file_path: Path to the JSON file with extracted elements
        min_confidence: Minimum confidence score to consider a match
        
    Returns:
        Dictionary mapping code block identifiers to their matches
    """
    logger = get_logger(__name__)
    from clean_and_format_code import clean_and_format_code
    from main import find_code_blocks
    
    try:
        # Get all code blocks from JSON
        code_blocks = find_code_blocks(json_file_path)
        logger.info("Starting code block matching for %d code blocks", len(code_blocks))
        
        all_matches = {}
        
        for i, code_block in enumerate(code_blocks):
            raw_text = code_block.get('text', '')
            cleaned_code = clean_and_format_code(raw_text)
            
            # Create a unique identifier for this code block
            block_id = f"code_block_{i+1}_page_{code_block.get('page_number', 'unknown')}"
            
            # Search for matches
            matches = search_code_in_pdf(pdf_path, json_file_path, cleaned_code, 
                                       code_block, min_confidence)
            
            if matches:
                all_matches[block_id] = matches
                log_success(f"Found {len(matches)} matches for {block_id}", logger)
            else:
                log_warning(f"No matches found for {block_id}", logger)
        
        log_success(f"Code matching completed: {len(all_matches)} blocks with matches found", logger)
        return all_matches
        
    except Exception as e:
        log_error(f"Error finding code matches: {e}", logger)
        return {}