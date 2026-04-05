from post_processing.tables_post_processing.convert_html_to_markdown import (
    convert_html_to_markdown,
)
from post_processing.tables_post_processing.replace_html_with_markdown import (
    replace_html_with_markdown,
)
from utils.logger import get_logger, log_error, log_success, log_warning

# Configure logging
logger = get_logger(__name__)


def handle_table_element(text, json_file_path):

    logger.info(f"HTML Content:\n{text}")

    # Convert HTML table to markdown
    markdown_content = convert_html_to_markdown(
        text, enable_table_plugin=True, verbose=True
    )

    if markdown_content:
        logger.info("Converted to Markdown:")
        logger.info("-" * 40)
        logger.info(markdown_content)
        logger.info("-" * 40)

        # Replace HTML with markdown in the corresponding markdown file
        logger.info("Replacing HTML with markdown in file...")
        success = replace_html_with_markdown(text, markdown_content, json_file_path)

        if success:
            log_success("HTML table successfully replaced with markdown!")
        else:
            log_error("Failed to replace HTML with markdown")
    else:
        log_error("Failed to convert HTML to markdown")
