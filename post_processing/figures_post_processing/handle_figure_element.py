from post_processing.figures_post_processing.process_figure import (
    get_figure_info_and_context, generate_figure_description, search_and_replace_figure_in_markdown
)
from utils.logger import get_logger, log_success, log_error, log_warning

def handle_figure_element(text, element, page, json_file_path):
    logger = get_logger(__name__)
    
    logger.info("Processing figure element")
    logger.debug("Figure Text/Reference:\n%s", text)
                    
    # Get figure information and context
    logger.info("Extracting figure information and context...")
    figure_info = get_figure_info_and_context(element, page.get("elements", []), json_file_path)
                    
    if figure_info["image_exists"]:
        log_success(f"Figure image found: {figure_info['relative_figure_path']}", logger)
        logger.info("Context length: %d characters", len(figure_info['context_text']))
                        
        # Generate figure description using LLM
        logger.info("Generating figure description using LLM...")
        description = generate_figure_description(
            figure_info["figure_path"], 
            figure_info["context_text"]
        )
                        
        if description:
            log_success("Generated figure description successfully", logger)
            logger.debug("Generated Description:\n%s", description)
                            
            # Replace figure text with description in markdown
            logger.info("Replacing figure text with description in markdown...")
            success = search_and_replace_figure_in_markdown(
                figure_info["figure_text"], 
                description, 
                json_file_path
            )
                            
            if success:
                log_success("Figure text successfully replaced with description!", logger)
            else:
                log_error("Failed to replace figure text with description", logger)
        else:
            log_error("Failed to generate figure description", logger)
    else:
        log_error(f"Figure image not found: {figure_info['relative_figure_path']}", logger)
        logger.debug("Expected path: %s", figure_info['figure_path'])
