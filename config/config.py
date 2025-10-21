"""
Configuration settings for the PDF parsing pipeline.

This module contains all configuration constants and settings used throughout
the PDF parsing pipeline application.
"""

# Directory paths
DATA_DIRECTORY = "./Data"  # Primary directory containing PDFs (searches recursively at any depth)         
OUTPUT_DIRECTORY = "./temp_result"  # Output directory (maintains same structure as input)

DOLPHIN_SCRIPT = "./Dolphin/demo_page_hf.py" # Do not modify this line
MODEL_PATH = "./Dolphin/hf_model" # Do not modify this line
HIERARCHY_JSON_DIRECTORY = "./section_hierarchy_pdfs"  # Directory containing TOC JSON files with section hierarchy
HTML_TO_MARKDOWN_DIR = "./post_processing/html-to-markdown"  # Directory containing html-to-markdown binaries

# Processing configuration flags
PROCESS_CODE_USING_LLM = False  # Set to True to process code segments with LLM (GPT-4o Vision API)
PROCESS_FIGURES_USING_LLM = False  # Set to True to process figure segments with LLM (GPT-4o Vision API)

# Segment processing configuration
SEGMENTS_TO_REFINE = ["tab"]  # Supported: "tab" (tables), "code" (code blocks), "fig" (figures)

# Additional configuration options (can be extended as needed)
# API Configuration
OPENAI_MODEL_VISION = "gpt-4o-mini"
OPENAI_MODEL_TEXT = "gpt-4o-mini"

# Processing limits
MAX_CONTEXT_LENGTH = 5000
MAX_DESCRIPTION_LENGTH = 1000

# Logging configuration
DEFAULT_LOG_LEVEL = "INFO"