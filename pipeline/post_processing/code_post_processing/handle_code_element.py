from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from post_processing.code_post_processing.clean_and_format_code import (
    clean_and_format_code,
)
from post_processing.code_post_processing.extract_code_from_pdf_page import (
    extract_code_from_pdf_page,
)
from post_processing.code_post_processing.replace_code_in_markdown_file import (
    replace_code_in_markdown_file,
)
from utils.get_markdown_file_path import get_markdown_file_path
from utils.get_pdf_file_path import get_pdf_file_path
from utils.logger import get_logger, log_error, log_success, log_warning


def _clean_code_fallback(text: str, logger) -> bool:
    """
    Fallback code cleaning when PDF file is not available.

    Args:
        text: Raw code text to clean
        logger: Logger instance

    Returns:
        True if cleaning successful, False otherwise
    """
    try:
        cleaned_code = clean_and_format_code(text)
        if cleaned_code:
            log_success("Code cleaned successfully", logger)
            logger.debug("Cleaned Code:\n%s", cleaned_code)
            return True
        else:
            log_error("Failed to clean code", logger)
            return False
    except Exception as e:
        log_error(f"Error cleaning code: {e}", logger)
        return False


def _resolve_file_paths(
    json_file_path: str, logger
) -> Tuple[Optional[str], Optional[Path]]:
    """
    Resolve PDF and markdown file paths from JSON file path.

    Args:
        json_file_path: Path to the JSON file
        logger: Logger instance

    Returns:
        Tuple of (pdf_file_path, markdown_file_path) or (None, None) if not found
    """
    # Get PDF file path
    pdf_file_path = get_pdf_file_path(json_file_path)
    if not pdf_file_path:
        log_warning(
            "Could not find corresponding PDF file - cannot perform PDF-based code replacement",
            logger,
        )
        return None, None

    log_success(f"Found PDF file: {pdf_file_path}", logger)

    # Get markdown file path
    markdown_file_path = get_markdown_file_path(json_file_path)
    if not markdown_file_path or not markdown_file_path.exists():
        log_error("Could not find markdown file for replacement", logger)
        return pdf_file_path, None

    log_success(f"Found markdown file: {markdown_file_path}", logger)
    return pdf_file_path, markdown_file_path


def _extract_and_compare_code(
    pdf_file_path: str, page_number: int, original_text: str, logger
) -> str:
    """
    Extract code from PDF page and compare with original.

    Args:
        pdf_file_path: Path to PDF file
        page_number: Page number (1-based)
        original_text: Original code text from JSON
        logger: Logger instance

    Returns:
        Best code version (either PDF-extracted or original)
    """
    logger.info("Step 2: Extracting original code from PDF page %d", page_number)
    pdf_page_index = page_number - 1  # Convert to 0-based indexing

    extracted_code = extract_code_from_pdf_page(
        pdf_file_path, pdf_page_index, original_text
    )

    if extracted_code != original_text:
        log_success("Successfully extracted different code from PDF!", logger)
        logger.info(
            "Original length: %d chars → PDF length: %d chars",
            len(original_text),
            len(extracted_code),
        )
        logger.debug(
            "PDF Code preview: %s",
            (
                extracted_code[:100] + "..."
                if len(extracted_code) > 100
                else extracted_code
            ),
        )
        return extracted_code
    else:
        logger.info("PDF extraction returned same code (no improvement found)")
        return original_text


def _replace_code_in_markdown(
    markdown_file_path: Path, cleaned_code: str, final_code: str, logger
) -> bool:
    """
    Replace code in markdown file with improved version.

    Args:
        markdown_file_path: Path to markdown file
        cleaned_code: Cleaned code to search for
        final_code: Final code to replace with
        logger: Logger instance

    Returns:
        True if replacement successful, False otherwise
    """
    logger.info("Step 3: Replacing code in markdown file")

    # Wrap in markdown code block format
    wrapped_code = f"```\n{final_code}\n```"

    # Find and replace the cleaned code in markdown
    success = replace_code_in_markdown_file(
        str(markdown_file_path), cleaned_code, wrapped_code
    )

    if success:
        log_success("Successfully replaced code in markdown!", logger)
        logger.info("Replacement summary:")
        logger.info("  • Used original PDF formatting (exact indentation)")
        logger.info("  • Preserved PDF character corrections")
        logger.info("  • Updated markdown code block")
        return True
    else:
        log_warning("Failed to replace code in markdown file", logger)
        return False


def _process_code_with_pdf(
    text: str, pdf_file_path: str, markdown_file_path: Path, page_number: int, logger
) -> bool:
    """
    Process code using PDF extraction and markdown replacement.

    Args:
        text: Original code text
        pdf_file_path: Path to PDF file
        markdown_file_path: Path to markdown file
        page_number: Page number
        logger: Logger instance

    Returns:
        True if processing successful, False otherwise
    """
    try:
        logger.info("Processing individual code block on page %d", page_number)

        # Step 1: Clean and format the code
        cleaned_code = clean_and_format_code(text)
        if not cleaned_code:
            log_error("Failed to clean code block", logger)
            return False

        log_success("Code cleaned successfully", logger)
        logger.debug("Cleaned Code:\n%s", cleaned_code)

        # Step 2: Extract original code from PDF page
        final_code = _extract_and_compare_code(pdf_file_path, page_number, text, logger)

        # Step 3: Replace code in markdown file
        success = _replace_code_in_markdown(
            markdown_file_path, cleaned_code, final_code, logger
        )

        if success:
            logger.info(
                "Individual code block processing completed for page %d", page_number
            )
            return True
        else:
            return False

    except Exception as e:
        log_error(f"Error during individual code processing: {e}", logger)
        return False


def handle_code_element(
    text: str,
    json_file_path: str,
    page_number: int,
    bbox: list,
    reading_order: int,
    label: str,
) -> bool:
    """
    Handles a single code element by extracting code from PDF, cleaning it, and replacing it in the markdown.

    Parameters:
        text (str): The text content of the element from JSON file.
        json_file_path (str): The path to the JSON file being processed.
        page_number (int): The page number where the element is located.
        bbox (list): The bounding box of the element.
        reading_order (int): The reading order of the element.
        label (str): The label/type of the element.

    Returns:
        bool: True if successful, False otherwise
    """
    logger = get_logger(__name__)
    logger.debug("Raw Code Content:\n%s", text)
    logger.info("Code found on page: %d", page_number)

    # Step 1: Resolve file paths
    pdf_file_path, markdown_file_path = _resolve_file_paths(json_file_path, logger)

    if not pdf_file_path:
        # Fallback: still clean the code even without PDF
        logger.info("Individual code cleaning will be attempted instead...")
        return _clean_code_fallback(text, logger)

    if not markdown_file_path:
        return False

    # Step 2: Process code with PDF extraction and markdown replacement
    return _process_code_with_pdf(
        text, pdf_file_path, markdown_file_path, page_number, logger
    )
