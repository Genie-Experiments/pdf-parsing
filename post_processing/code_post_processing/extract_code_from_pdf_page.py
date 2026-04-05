import pymupdf

from post_processing.code_post_processing.pdf_code_search import (
    fuzzy_match_similarity,
    normalize_text_for_comparison,
)
from utils.logger import get_logger, log_error, log_success, log_warning


def extract_code_from_pdf_page(
    pdf_path: str, page_number: int, target_code: str
) -> str:
    """
    Extract original code from a specific PDF page using fuzzy matching.

    Args:
        pdf_path: Path to the PDF file
        page_number: Page number (0-based indexing for PyMuPDF)
        target_code: The code text to search for

    Returns:
        Original code text from PDF or the target_code if not found
    """
    logger = get_logger(__name__)

    try:
        logger.debug(
            "Opening PDF and extracting text from page %d (PDF index %d)",
            page_number + 1,
            page_number,
        )

        # Open PDF and get the specific page
        pdf_doc = pymupdf.open(pdf_path)

        if page_number >= len(pdf_doc):
            log_warning(
                f"Page {page_number + 1} not found in PDF (total pages: {len(pdf_doc)})",
                logger,
            )
            pdf_doc.close()
            return target_code

        page = pdf_doc[page_number]
        page_text = page.get_text()
        pdf_doc.close()

        logger.debug("Successfully extracted text from page %d", page_number + 1)
        logger.debug("Page text length: %d characters", len(page_text))

        # Normalize target code for comparison
        target_normalized = normalize_text_for_comparison(target_code)
        target_lines = target_code.strip().split("\n")

        logger.debug("Searching for code with %d lines in page text", len(target_lines))

        # Split page text into lines for analysis
        page_lines = page_text.split("\n")

        # Try different window sizes around the expected code length
        best_match = None
        best_score = 0.0

        for window_size in [
            len(target_lines),
            len(target_lines) + 2,
            len(target_lines) - 1,
        ]:
            if window_size <= 0:
                continue

            for i in range(len(page_lines) - window_size + 1):
                # Extract a segment of lines from the page
                segment_lines = page_lines[i : i + window_size]
                segment_text = "\n".join(segment_lines)

                # Skip empty segments
                if not segment_text.strip():
                    continue

                # Normalize segment for comparison
                segment_normalized = normalize_text_for_comparison(segment_text)

                # Calculate similarity score
                score = fuzzy_match_similarity(target_normalized, segment_normalized)

                # Bonus for exact line count match
                if len(segment_lines) == len(target_lines):
                    score *= 1.1

                # Bonus for technical content indicators
                if any(
                    keyword in segment_text.lower()
                    for keyword in [
                        "configure",
                        "terminal",
                        "def ",
                        "class ",
                        "import",
                        "function",
                        "command",
                    ]
                ):
                    score *= 1.05

                if score > best_score:
                    best_score = score
                    best_match = segment_text

        # Return best match if confidence is high enough
        if best_match and best_score > 0.6:  # 60% similarity threshold
            log_success(f"Found matching code with {best_score:.2f} confidence", logger)
            logger.debug(
                "Matched code preview: %s",
                best_match[:100] + "..." if len(best_match) > 100 else best_match,
            )
            return best_match.strip()
        else:
            log_warning(f"No good match found (best score: {best_score:.2f})", logger)
            logger.info("Returning original code from JSON")
            return target_code

    except Exception as e:
        log_error(f"Error extracting from PDF page: {e}", logger)
        return target_code
