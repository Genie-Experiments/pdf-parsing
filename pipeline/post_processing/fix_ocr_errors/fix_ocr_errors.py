import json
import os
import re
import sys
import traceback
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from utils.get_markdown_file_path import get_markdown_file_path
from utils.logger import get_logger, log_error, log_success, log_warning

# Configure logging
logger = get_logger(__name__)


class OCRErrorFixer:
    def __init__(
        self,
        json_path: str,
        extracted_text_path: str,
        markdown_path: str,
        length_similarity_threshold: float = 0.7,
    ):
        """
        Initialize the OCR Error Fixer

        Args:
            json_path: Path to the JSON file with OCR errors
            extracted_text_path: Path to the accurate extracted text file
            markdown_path: Path to the markdown file to fix
            length_similarity_threshold: Minimum ratio of lengths for fuzzy matching
        """
        self.json_path = json_path
        self.extracted_text_path = extracted_text_path
        self.markdown_path = markdown_path
        self.length_similarity_threshold = length_similarity_threshold

        # Load data
        with open(json_path, "r", encoding="utf-8") as f:
            self.json_data = json.load(f)

        with open(extracted_text_path, "r", encoding="utf-8") as f:
            self.accurate_text = f.read()

        with open(markdown_path, "r", encoding="utf-8") as f:
            self.markdown_content = f.read()

        # Parse the text file to extract page-wise content
        self.page_text_map = self._parse_text_file_by_pages()

        # Parse markdown to extract page-wise content
        self.page_markdown_map = self._parse_markdown_by_pages()

    def _parse_text_file_by_pages(self) -> Dict[int, str]:
        """
        Parse the text file and extract content for each page

        Returns:
            Dictionary mapping page_number to page text content
        """
        page_map = {}
        current_page = None
        current_content = []

        lines = self.accurate_text.split("\n")

        for line in lines:
            # Check for page marker
            page_match = re.match(r"^=== Page (\d+) ===", line)
            if page_match:
                # Save previous page content if exists
                if current_page is not None:
                    page_map[current_page] = "\n".join(current_content)

                # Start new page
                current_page = int(page_match.group(1))
                current_content = []
            else:
                # Accumulate content for current page
                if current_page is not None:
                    current_content.append(line)

        # Save last page
        if current_page is not None:
            page_map[current_page] = "\n".join(current_content)

        return page_map

    def _parse_markdown_by_pages(self) -> Dict[int, Tuple[str, int, int]]:
        """
        Parse markdown file and extract content for each page

        Returns:
            Dictionary mapping page_number to tuple of (page_content, start_pos, end_pos)
        """
        page_map = {}

        # Split by page breaks
        page_breaks = list(
            re.finditer(r"<!-- page_break_(\d+) -->", self.markdown_content)
        )

        # Page 1 content (before first page_break)
        if page_breaks:
            first_break = page_breaks[0]
            page_1_content = self.markdown_content[: first_break.start()]
            page_map[1] = (page_1_content, 0, first_break.start())

        # Process subsequent pages
        for i, page_break in enumerate(page_breaks):
            page_num = int(page_break.group(1))
            start_pos = page_break.end()

            # Find end position (next page break or end of document)
            if i + 1 < len(page_breaks):
                end_pos = page_breaks[i + 1].start()
            else:
                end_pos = len(self.markdown_content)

            page_content = self.markdown_content[start_pos:end_pos]
            page_map[page_num + 1] = (page_content, start_pos, end_pos)

        return page_map

    def is_table_of_contents(self, text: str) -> bool:
        """
        Heuristics to detect table of contents entries
        """
        # Check for page numbers at the end
        if re.search(r"\d+\s*$", text.strip()):
            return True

        # Check for common TOC patterns
        toc_patterns = [
            r"^Table of Contents",
            r"\.{3,}",  # Multiple dots (leader dots)
            r"on page \d+",
            r"see page \d+",
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
        """
        # Define separator patterns - only line breaks
        separators = [
            r"\r\n",  # Windows line ending (must come first)
            r"\n",  # Unix/Linux line ending
            r"\r",  # Mac classic line ending
        ]

        # Create a combined pattern
        combined_pattern = "|".join(f"(?:{sep})" for sep in separators)

        # Handle hyphenated line breaks specially
        # Replace -\n with empty string to join hyphenated words
        text = re.sub(r"-\s*\n\s*", "", text)

        # Split by the combined pattern
        lines = re.split(combined_pattern, text)

        # Clean up the lines - only basic cleanup since we only split on line breaks
        cleaned_lines = []
        for line in lines:
            line = line.strip()

            # Only keep non-empty lines with substantial content
            if line and len(line) > 1:
                cleaned_lines.append(line)

        return cleaned_lines

    def fuzzy_match_in_page(
        self, ocr_text: str, page_content: str, threshold: float = 0.6
    ) -> Optional[Tuple[str, float]]:
        """
        Find the best fuzzy match for ocr_text in a specific page's content

        Args:
            ocr_text: Text with potential OCR errors
            page_content: The accurate text content of the page
            threshold: Minimum similarity ratio (0-1)

        Returns:
            Tuple of (matched_text, similarity_score) or None
        """
        ocr_text_clean = ocr_text.strip()

        # Extract actual text lines from the page content (ignore structural markers)
        text_lines = []
        for line in page_content.split("\n"):
            line = line.strip()
            # Extract text after "Text: " marker
            if line.startswith("Text: "):
                text_lines.append(line[6:])  # Remove "Text: " prefix
            elif line and not line.startswith(("---", "===", "Type:", "Page Size:")):
                # Include other non-structural lines
                text_lines.append(line)

        best_match = None
        best_ratio = 0

        for line in text_lines:
            if len(line) < 3:
                continue

            # Quick length filter - only check lines with similar length
            length_ratio = min(len(ocr_text_clean), len(line)) / max(
                len(ocr_text_clean), len(line)
            )
            if length_ratio < self.length_similarity_threshold:
                continue

            # Calculate similarity
            ratio = SequenceMatcher(None, ocr_text_clean.lower(), line.lower()).ratio()

            if ratio > best_ratio:
                best_ratio = ratio
                best_match = line

        if best_ratio >= threshold:
            return (best_match, best_ratio)

        return None

    def extract_texts_from_json(
        self, skip_labels: List[str] = None
    ) -> List[Tuple[str, dict]]:
        """
        Extract all text elements from JSON with page information

        Args:
            skip_labels: List of labels to skip (default: ['code', 'tab'])

        Returns:
            List of tuples: (text, metadata)
        """
        if skip_labels is None:
            skip_labels = ["code", "tab"]

        texts_to_fix = []

        for page in self.json_data.get("pages", []):
            page_num = page.get("page_number")

            for element in page.get("elements", []):
                label = element.get("label", "")
                text = element.get("text", "")

                # Skip specified labels (code, table)
                if label in skip_labels:
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
                    # if len(line) > self.min_text_length:
                    texts_to_fix.append(
                        (
                            line,
                            {"page": page_num, "label": label, "original_text": text},
                        )
                    )

        return texts_to_fix

    def replace_in_markdown_page(
        self, page_num: int, ocr_text: str, accurate_text: str
    ) -> bool:
        """
        Replace OCR text with accurate text in a specific markdown page

        Args:
            page_num: Page number where replacement should occur
            ocr_text: Text to find and replace
            accurate_text: Replacement text

        Returns:
            Boolean indicating if replacement was made
        """
        if page_num not in self.page_markdown_map:
            return False

        page_content, start_pos, end_pos = self.page_markdown_map[page_num]

        # Try exact match first, then word-boundary regex
        if ocr_text in page_content:
            updated_content = page_content.replace(ocr_text, accurate_text, 1)
        else:
            ocr_text_escaped = re.escape(ocr_text.strip())
            pattern = r"\b" + ocr_text_escaped + r"\b"
            if not re.search(pattern, page_content):
                return False
            updated_content = re.sub(pattern, accurate_text, page_content, count=1)

        delta = len(updated_content) - len(page_content)

        # Update the markdown content
        self.markdown_content = (
            self.markdown_content[:start_pos]
            + updated_content
            + self.markdown_content[end_pos:]
        )

        # Update positions incrementally — no need to re-parse the whole document
        self.page_markdown_map[page_num] = (updated_content, start_pos, end_pos + delta)
        if delta != 0:
            for pnum, (pcontent, s, e) in list(self.page_markdown_map.items()):
                if s >= end_pos:
                    self.page_markdown_map[pnum] = (pcontent, s + delta, e + delta)

        return True

    def fix_markdown(
        self,
        output_path: str,
        min_similarity: float = 0.65,
        skip_labels: List[str] = None,
    ) -> Tuple[str, List[Dict]]:
        """
        Fix OCR errors in markdown using accurate text with page-aware processing

        Flow:
        1. Read raw text from JSON file (page by page, element by element)
        2. Separate text if it has line separators
        3. Search each text in the txt file on the specific page only
        4. If found with similarity >= threshold, search in markdown on that page
        5. Replace markdown text with accurate text from txt file

        Args:
            output_path: Path to save the corrected markdown
            min_similarity: Minimum similarity threshold for replacements
            skip_labels: List of labels to skip during extraction

        Returns:
            Tuple of (corrected_markdown, replacements_list)
        """
        # Step 1 & 2: Extract texts from JSON with page info and line separation
        texts_to_fix = self.extract_texts_from_json(skip_labels)

        replacements = []

        logger.info(f"Processing {len(texts_to_fix)} text segments...")

        for idx, (ocr_text, metadata) in enumerate(texts_to_fix):
            if idx % 100 == 0:
                logger.info(f"Progress: {idx}/{len(texts_to_fix)}")

            page_num = metadata["page"]

            # Step 3: Search in txt file on the specific page only
            if page_num not in self.page_text_map:
                continue

            page_text_content = self.page_text_map[page_num]

            # Find accurate version in the page's text content
            match_result = self.fuzzy_match_in_page(
                ocr_text, page_text_content, threshold=min_similarity
            )

            if match_result:
                accurate_version, similarity = match_result

                # Only process if texts are different
                if ocr_text.strip() != accurate_version.strip():
                    # Quality check: Only replace if the "correction" is actually better
                    ocr_clean = ocr_text.strip()
                    accurate_clean = accurate_version.strip()

                    # Skip replacement if the accurate text is shorter than OCR text
                    # This means OCR text is more complete, so don't replace it
                    ocr_length = len(ocr_clean)
                    accurate_length = len(accurate_clean)

                    if accurate_length < ocr_length:
                        continue

                    # Step 4 & 5: Search and replace in markdown on that specific page
                    replacement_made = self.replace_in_markdown_page(
                        page_num, ocr_text.strip(), accurate_version
                    )

                    if replacement_made:
                        replacements.append(
                            {
                                "page": page_num,
                                "ocr_text": ocr_text,
                                "corrected_text": accurate_version,
                                "similarity": similarity,
                            }
                        )

        # Save corrected markdown
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(self.markdown_content)

        # Save replacement log
        log_path = output_path.replace(".md", "_corrections.json")
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(replacements, f, indent=2, ensure_ascii=False)

        log_success(f"Corrected markdown saved to: {output_path}")
        log_success(f"Made {len(replacements)} corrections")
        log_success(f"Correction log saved to: {log_path}")

        return self.markdown_content, replacements


def fix_ocr_errors_batch(
    results_directory: str,
    raw_pdf_text_directory: str,
    min_similarity: float = 0.65,
    skip_labels: List[str] = None,
    **fixer_kwargs,
):
    """
    Batch process OCR error fixing for all files in the results directory.

    Args:
        results_directory: Directory containing JSON and markdown files from processing
        raw_pdf_text_directory: Directory containing extracted raw text files
        min_similarity: Minimum similarity threshold for replacements
        skip_labels: List of labels to skip during extraction
        **fixer_kwargs: Additional arguments to pass to OCRErrorFixer constructor

    Returns:
        Boolean indicating success
    """
    # Convert to absolute paths to avoid path resolution issues
    results_directory = os.path.abspath(results_directory)
    raw_pdf_text_directory = os.path.abspath(raw_pdf_text_directory)

    logger.info("Starting batch OCR error correction...")
    logger.info(f"Results directory: {results_directory}")
    logger.info(f"Raw PDF text directory: {raw_pdf_text_directory}")
    logger.info(f"Minimum similarity threshold: {min_similarity}")
    logger.info("-" * 60)

    # Check if directories exist
    if not os.path.exists(results_directory):
        log_error(f"Results directory '{results_directory}' does not exist!")
        return False

    if not os.path.exists(raw_pdf_text_directory):
        log_error(f"Raw PDF text directory '{raw_pdf_text_directory}' does not exist!")
        return False

    # Find all JSON files in the results directory (recursively)
    json_files = []
    for root, dirs, files in os.walk(results_directory):
        for file in files:
            if file.lower().endswith(".json") and not file.endswith(
                "_corrections.json"
            ):
                json_files.append(os.path.join(root, file))

    if not json_files:
        log_warning(f"No JSON files found in '{results_directory}'")
        return True

    logger.info(f"Found {len(json_files)} JSON files to process")

    successful_corrections = 0
    failed_corrections = 0
    skipped_corrections = 0

    for i, json_path in enumerate(json_files, 1):
        rel_json_path = os.path.relpath(json_path, results_directory)
        try:
            logger.info(f"[{i}/{len(json_files)}] Processing: {rel_json_path}")

            # Determine the corresponding markdown and text file paths
            base_name = os.path.splitext(os.path.basename(json_path))[0]

            # Use utility function to get markdown file path
            markdown_path = str(get_markdown_file_path(json_path))

            # Get the path components
            json_path_obj = Path(json_path)

            # Navigate up from recognition_json to get the parent directory
            parent_of_recognition = json_path_obj.parent.parent

            # Get the relative path from results directory to this parent
            rel_path_to_parent = os.path.relpath(
                parent_of_recognition, results_directory
            )

            # Construct the text file path
            # Text files are stored in category directory, not in subdirectory with same name
            if rel_path_to_parent == ".":
                text_path = os.path.join(raw_pdf_text_directory, base_name + ".txt")
            else:
                # Extract just the category part (first directory) from the relative path
                category = rel_path_to_parent.split(os.sep)[0]
                text_path = os.path.join(
                    raw_pdf_text_directory, category, base_name + ".txt"
                )

            # Check if required files exist
            if not os.path.exists(markdown_path):
                log_warning(f"Skipping (markdown file not found): {markdown_path}")
                skipped_corrections += 1
                continue

            if not os.path.exists(text_path):
                log_warning(f"Skipping (text file not found): {text_path}")
                skipped_corrections += 1
                continue

            # Initialize OCR fixer and process
            fixer = OCRErrorFixer(json_path, text_path, markdown_path, **fixer_kwargs)

            # Use the original markdown path to modify in place
            output_path = markdown_path

            # Fix OCR errors
            corrected_md, replacements = fixer.fix_markdown(
                output_path, min_similarity, skip_labels
            )

            successful_corrections += 1
            log_success(
                f"Fixed {len(replacements)} errors, saved to: {os.path.basename(output_path)}"
            )

        except Exception as e:
            failed_corrections += 1
            log_error(f"Error processing {rel_json_path}: {str(e)}")
            logger.debug("Traceback:\n%s", traceback.format_exc())

    # Print summary
    logger.info("=" * 60)
    logger.info("OCR Error Correction Summary:")
    logger.info(f"Total JSON files found: {len(json_files)}")
    logger.info(f"Successfully processed: {successful_corrections}")
    logger.info(f"Skipped files: {skipped_corrections}")
    logger.info(f"Failed corrections: {failed_corrections}")

    return failed_corrections == 0


# Example usage
if __name__ == "__main__":
    # If run directly, import config and use default settings
    import sys

    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "config"))
    from config import OUTPUT_DIRECTORY, RAW_PDF_TEXT_DIR

    # Run batch processing with default directories
    success = fix_ocr_errors_batch(
        OUTPUT_DIRECTORY,
        RAW_PDF_TEXT_DIR,
        min_similarity=0.75,
        length_similarity_threshold=0.3,
    )

    if success:
        log_success("OCR error correction completed successfully!")
    else:
        log_error("OCR error correction failed!")

    sys.exit(0 if success else 1)
