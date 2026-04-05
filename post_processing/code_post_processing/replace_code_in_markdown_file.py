import re

from post_processing.code_post_processing.pdf_code_search import (
    fuzzy_match_similarity,
    normalize_text_for_comparison,
)
from utils.logger import get_logger, log_error, log_success, log_warning


def replace_code_in_markdown_file(
    markdown_file_path: str, old_code: str, new_code: str
) -> bool:
    """
    Replace old code with new code in markdown file - ONLY within code blocks to prevent text corruption.

    Args:
        markdown_file_path: Path to the markdown file
        old_code: The code to be replaced (cleaned code)
        new_code: The new code to replace with (PDF extracted code in markdown format)

    Returns:
        True if replacement was successful, False otherwise
    """
    logger = get_logger(__name__)

    try:
        logger.info("Reading markdown file: %s", markdown_file_path)

        # Read the markdown file
        with open(markdown_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Normalize old_code for better matching (remove surrounding ``` if present)
        old_code_normalized = old_code.strip()
        if old_code_normalized.startswith("```") and old_code_normalized.endswith(
            "```"
        ):
            # Extract inner code content only
            lines = old_code_normalized.split("\n")
            if len(lines) >= 3:
                old_code_normalized = "\n".join(lines[1:-1])

        # CRITICAL: Only look for code blocks, never replace regular text
        code_block_pattern = r"```[\s\S]*?```"
        code_blocks = list(re.finditer(code_block_pattern, content))

        logger.info("Found %d code blocks to search through", len(code_blocks))

        if not code_blocks:
            log_warning("No code blocks found in markdown file", logger)
            return False

        old_normalized = normalize_text_for_comparison(old_code_normalized)
        replacements_made = 0

        # Search through each code block individually
        for i, match in enumerate(code_blocks):
            block_content = match.group(0)
            logger.debug("Checking code block %d/%d", i + 1, len(code_blocks))

            # Extract just the code inside the ``` markers
            block_lines = block_content.split("\n")
            if len(block_lines) < 3:  # Need at least opening ```, content, closing ```
                continue

            # Remove ``` markers and get inner content
            inner_code = "\n".join(block_lines[1:-1])

            # First try exact match for efficiency
            if old_code_normalized.strip() == inner_code.strip():
                log_success(f"Found exact match in code block {i+1}", logger)
                content = content.replace(
                    block_content, new_code.strip(), 1
                )  # Replace only first occurrence
                replacements_made += 1
                break

            # If no exact match, try fuzzy matching
            inner_normalized = normalize_text_for_comparison(inner_code)
            similarity = fuzzy_match_similarity(old_normalized, inner_normalized)

            logger.debug("Code block %d similarity: %.2f", i + 1, similarity)

            if similarity > 0.7:  # 70% similarity threshold for code blocks only
                log_success(
                    f"Found fuzzy match in code block {i+1} with {similarity:.2f} confidence",
                    logger,
                )
                content = content.replace(
                    block_content, new_code.strip(), 1
                )  # Replace only first occurrence
                replacements_made += 1
                break

        if replacements_made > 0:
            # Write back to file
            with open(markdown_file_path, "w", encoding="utf-8") as f:
                f.write(content)
            log_success(
                f"Successfully made {replacements_made} replacement(s) in markdown file",
                logger,
            )
            logger.info("Only code blocks were modified - regular text preserved")
            return True
        else:
            log_warning("No suitable code block matches found for replacement", logger)
            return False

    except Exception as e:
        log_error(f"Error replacing code in markdown: {str(e)}", logger)
        return False
