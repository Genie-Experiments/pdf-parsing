"""
Configuration settings for the PDF parsing pipeline.

This module contains all configuration constants and settings used throughout
the PDF parsing pipeline application.
"""

# Directory paths
DATA_DIRECTORY = "./Data"  # Primary directory containing PDFs (searches recursively at any depth)
                          # Can be relative path (from project root) or absolute path
                          # Examples: "./Data", "/path/to/pdfs", "C:/Users/PDFs"
                          # 
                          # RECURSIVE SEARCH: The system will find PDFs no matter how deep 
                          # they are nested in subdirectories under this path.
                          # Example structure:
                          #   ./Data/
                          #     ├── document1.pdf
                          #     ├── category1/
                          #     │   ├── document2.pdf
                          #     │   └── subcategory/
                          #     │       └── document3.pdf
                          #     └── category2/
                          #         └── document4.pdf
                          # All PDFs above will be found regardless of their depth.
OUTPUT_DIRECTORY = "./Results"  # Output directory (maintains same structure as input)
DOLPHIN_SCRIPT = "./Dolphin/demo_page_hf.py" # Do not modify this line
MODEL_PATH = "./Dolphin/hf_model" # Do not modify this line
TOC_JSON_DIRECTORY = "./toc_json_files"  # Directory containing TOC JSON files with section hierarchy

# Processing configuration flags
PROCESS_CODE_USING_LLM = False  # Set to True to process code segments with LLM (GPT-4o Vision API)
                               # When True: Crops code sections from page images and uses OpenAI GPT-4o Vision
                               #           for high-quality code extraction and formatting
                               # When False: Uses traditional text-based code cleaning and formatting
                               # Requires OPENAI_API_KEY environment variable if enabled

PROCESS_FIGURES_USING_LLM = False  # Set to True to process figure segments with LLM (GPT-4o Vision API)

# Segment processing configuration
SEGMENTS_TO_REFINE = ["tab", "code", "fig"]  # Supported: "tab" (tables), "code" (code blocks), "fig" (figures)

# Additional configuration options (can be extended as needed)
# API Configuration
OPENAI_MODEL_VISION = "gpt-4o-mini"
OPENAI_MODEL_TEXT = "gpt-4o-mini"

# Processing limits
MAX_CONTEXT_LENGTH = 5000
MAX_DESCRIPTION_LENGTH = 1000

# Logging configuration
DEFAULT_LOG_LEVEL = "INFO"
