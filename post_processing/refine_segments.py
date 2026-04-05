import json

from post_processing.code_post_processing.handle_code_element import handle_code_element
from post_processing.figures_post_processing.handle_figure_element import (
    handle_figure_element,
)
from post_processing.tables_post_processing.handle_table_element import (
    handle_table_element,
)
from utils.get_markdown_file_path import get_markdown_file_path
from utils.logger import get_logger


def refine_segments(
    json_file_path,
    segments_to_extract: list,
    process_code_using_llm=False,
    process_figures_using_llm=False,
):
    logger = get_logger(__name__)

    # Load the recognition.json file
    with open(json_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Loop through pages and elements
    for page in data.get("pages", []):
        page_number = page.get("page_number")
        logger.debug("Processing page %d", page_number)

        for element in page.get("elements", []):
            label = element.get("label")

            if label in segments_to_extract:  # check for specified segments
                bbox = element.get("bbox")
                text = element.get("text")
                reading_order = element.get("reading_order")

                logger.info("Found %s element:", label.upper())
                logger.debug("  Bounding Box: %s", bbox)
                logger.debug("  Reading Order: %s", reading_order)

                # Special handling for table elements
                if label == "tab":
                    handle_table_element(text, json_file_path)

                # Special handling for code elements
                elif label == "code":
                    handle_code_element(
                        text, json_file_path, page_number, bbox, reading_order, label
                    )

                # Special handling for figure elements
                elif label == "fig" and process_figures_using_llm:
                    handle_figure_element(text, element, page, json_file_path)

                # Special handling for catalogue elements
                elif label == "catalogue":
                    markdown_file_path = get_markdown_file_path(json_file_path)

                    # Read the markdown file
                    if markdown_file_path.exists():
                        with open(markdown_file_path, "r", encoding="utf-8") as md_file:
                            markdown_content = md_file.read()

                        if text:
                            # Try exact match first
                            if text in markdown_content:
                                markdown_content = markdown_content.replace(text, "")
                                logger.info("Removed catalogue text from markdown file")

                                # Write the updated content back to the markdown file
                                with open(
                                    markdown_file_path, "w", encoding="utf-8"
                                ) as md_file:
                                    md_file.write(markdown_content)
                            else:
                                # Try with newlines converted to spaces (common in markdown processing)
                                text_with_spaces = text.replace("\n", " ")
                                if text_with_spaces in markdown_content:
                                    markdown_content = markdown_content.replace(
                                        text_with_spaces, ""
                                    )
                                    logger.info(
                                        "Removed catalogue text from markdown file (matched with spaces)"
                                    )

                                    # Write the updated content back to the markdown file
                                    with open(
                                        markdown_file_path, "w", encoding="utf-8"
                                    ) as md_file:
                                        md_file.write(markdown_content)
                                else:
                                    logger.warning(
                                        "Catalogue text not found in markdown file"
                                    )
                        else:
                            logger.warning("Catalogue element has no text")
                    else:
                        logger.warning(
                            "Markdown file not found at: %s", markdown_file_path
                        )
