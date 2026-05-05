"""
LLM-based Code Processing Module for PDF Parsing Pipeline

This module handles the extraction and processing of code blocks using Large Language Models.
It crops code sections from page images and sends them to OpenAI's Vision API for accurate
code extraction and formatting.
"""

import base64
import io
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import openai
from dotenv import load_dotenv

from utils.logger import get_logger, log_error, log_success, log_warning

# Load environment variables
load_dotenv()

# Constants
VISION_MODEL = "gpt-4o"
SUPPORTED_IMAGE_FORMATS = [".png", ".jpg", ".jpeg", ".gif", ".bmp"]
MAX_IMAGE_SIZE = (1024, 1024)  # Max size for API


class LLMCodeProcessor:
    """
    Main class for processing code blocks using LLM vision capabilities.
    """

    def __init__(self):
        """Initialize the LLMCodeProcessor with API configuration."""
        self.logger = get_logger(__name__)
        self.openai_client = None
        self._initialize_openai_client()

    def _initialize_openai_client(self) -> None:
        """Initialize OpenAI client if API key is available."""
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                self.openai_client = openai.OpenAI(api_key=api_key)
                log_success(
                    "OpenAI client initialized successfully for code processing",
                    self.logger,
                )
            except Exception as e:
                log_error(f"Failed to initialize OpenAI client: {e}", self.logger)
                self.openai_client = None
        else:
            log_warning(
                "OpenAI API key not found in environment variables", self.logger
            )

    def process_code_with_llm(
        self, element: Dict[str, Any], json_file_path: str
    ) -> Optional[str]:
        """
        Process code element using LLM vision capabilities.

        Args:
            element: The code element from JSON recognition data
            json_file_path: Path to the JSON file

        Returns:
            Extracted and formatted code string, or None if processing fails
        """
        try:
            if not self.openai_client:
                log_warning(
                    "OpenAI client not available, falling back to text-based processing",
                    self.logger,
                )
                return None

            # Get PDF file name and page information
            self.logger.info("Starting LLM-based code processing")
            pdf_name = self._extract_pdf_name(json_file_path)
            page_number = self._get_page_number_from_context(element, json_file_path)

            if not pdf_name or not page_number:
                log_error("Could not determine PDF name or page number", self.logger)
                return None

            self.logger.debug(
                "Processing code for PDF: %s, page: %d", pdf_name, page_number
            )

            # Find the page image
            page_image_path = self._find_page_image(pdf_name, page_number)
            if not page_image_path:
                log_error(
                    f"Could not find page image for {pdf_name}, page {page_number}",
                    self.logger,
                )
                return None

            # Crop the code section from the image using padded_bbox for better accuracy
            bbox_to_use = element.get("padded_bbox") or element.get("bbox", [])
            self.logger.debug(
                "Using %s for cropping",
                "padded_bbox" if element.get("padded_bbox") else "bbox",
            )
            cropped_image = self._crop_code_section(page_image_path, bbox_to_use)
            if not cropped_image:
                log_error("Failed to crop code section from image", self.logger)
                return None

            # Send to OpenAI Vision API
            extracted_code = self._extract_code_with_vision_api(cropped_image)

            if extracted_code:
                log_success("Successfully extracted code using LLM vision", self.logger)
                self.logger.debug(
                    "Extracted code length: %d characters", len(extracted_code)
                )
                return extracted_code
            else:
                log_warning("Failed to extract code using LLM vision", self.logger)
                return None

        except Exception as e:
            log_error(f"Error processing code with LLM: {e}", self.logger)
            return None

    def _extract_pdf_name(self, json_file_path: str) -> Optional[str]:
        """Extract PDF file name from JSON file path or content."""
        try:
            # Try to get from JSON file content first
            with open(json_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                source_file = data.get("source_file", "")
                if source_file:
                    return Path(source_file).stem

            # Fallback to JSON file name
            json_path = Path(json_file_path)
            return json_path.stem

        except Exception as e:
            log_error(f"Error extracting PDF name: {e}", self.logger)
            return None

    def _get_page_number_from_context(
        self, element: Dict[str, Any], json_file_path: str
    ) -> Optional[int]:
        """Get page number for the given element."""
        try:
            with open(json_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Search for the element in pages to find page number
            for page in data.get("pages", []):
                for page_element in page.get("elements", []):
                    if page_element.get("bbox") == element.get(
                        "bbox"
                    ) and page_element.get("reading_order") == element.get(
                        "reading_order"
                    ):
                        return page.get("page_number")

            log_error("Could not find page number for element", self.logger)
            return None

        except Exception as e:
            log_error(f"Error getting page number: {e}", self.logger)
            return None

    def _find_page_image(self, pdf_name: str, page_number: int) -> Optional[Path]:
        """Find the page image in the Processed-Images-By-Dolphin folder."""
        try:
            # Construct the expected image path
            images_dir = Path("./Processed-Images-By-Dolphin") / pdf_name

            # Try different possible filename formats
            possible_filenames = [
                f"page-{page_number}.png",
                f"page_{page_number}.png",
                f"{pdf_name}_page_{page_number}.png",
                f"{pdf_name}-page-{page_number}.png",
            ]

            for filename in possible_filenames:
                image_path = images_dir / filename
                if image_path.exists():
                    log_success(f"Found page image: {image_path}", self.logger)
                    return image_path

            log_error(
                f"No page image found for {pdf_name}, page {page_number}", self.logger
            )
            self.logger.debug("Searched in: %s", images_dir)
            self.logger.debug("Tried filenames: %s", possible_filenames)

            return None

        except Exception as e:
            log_error(f"Error finding page image: {e}", self.logger)
            return None

    def _crop_code_section(
        self, image_path: Path, bbox: List[float]
    ) -> Optional[bytes]:
        """Crop the code section from the page image based on bounding box."""
        try:
            if not bbox or len(bbox) != 4:
                log_error("Invalid bounding box provided", self.logger)
                return None

            self.logger.debug("Cropping image with bbox: %s", bbox)

            # Use OpenCV cropping for high quality results
            from utils.image_cropping import crop_image_opencv

            result = crop_image_opencv(
                image_path=image_path,
                bbox=bbox,
                padding=0,  # No extra padding since we're using padded_bbox
            )

            if result:
                log_success(
                    f"Successfully cropped code section: {len(result)} bytes",
                    self.logger,
                )
                return result
            else:
                log_error("All cropping methods failed", self.logger)
                return None

        except Exception as e:
            log_error(f"Error cropping code section: {e}", self.logger)
            return None

    def _extract_code_with_vision_api(self, image_bytes: bytes) -> Optional[str]:
        """Extract code from cropped image using OpenAI Vision API."""
        try:
            self.logger.info("Preparing image for Vision API processing")

            # Encode image to base64
            base64_image = base64.b64encode(image_bytes).decode("utf-8")
            self.logger.debug(
                "Image encoded to base64: %d characters", len(base64_image)
            )

            # Prepare the prompt
            system_prompt = """You are a code extraction expert. Your task is to analyze the provided image and extract any code, configuration, or commands that you see.

Instructions:
1. Extract ALL visible code/text exactly as it appears
2. Preserve formatting, indentation, and structure
3. If it's code, wrap it in appropriate code blocks with language detection
4. If it's configuration, preserve the hierarchical structure
5. If it's command output, maintain the original formatting
6. Do not add explanations or comments unless they're part of the original code
7. If no code is visible, respond with "No code found in image"

Return only the extracted code without any additional text or explanations."""

            self.logger.info("Calling OpenAI Vision API for code extraction")

            # Make API call
            response = self.openai_client.chat.completions.create(
                model=VISION_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Please extract the code from this image:",
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                },
                            },
                        ],
                    },
                ],
                max_tokens=2000,
                temperature=0.1,
            )

            extracted_code = response.choices[0].message.content.strip()

            if extracted_code and extracted_code != "No code found in image":
                log_success("Successfully extracted code using Vision API", self.logger)
                self.logger.debug(
                    "Vision API response length: %d characters", len(extracted_code)
                )
                return extracted_code
            else:
                log_warning("No code found in image by Vision API", self.logger)
                return None

        except Exception as e:
            log_error(f"Error calling OpenAI Vision API: {e}", self.logger)
            return None


# Lazily initialized singleton — not created at import time
_code_processor: Optional[LLMCodeProcessor] = None


def _get_code_processor() -> LLMCodeProcessor:
    global _code_processor
    if _code_processor is None:
        _code_processor = LLMCodeProcessor()
    return _code_processor


def process_code_with_llm(
    element: Dict[str, Any], json_file_path: str
) -> Optional[str]:
    """
    Convenience function to process code with LLM.

    Args:
        element: The code element from JSON recognition data
        json_file_path: Path to the JSON file

    Returns:
        Extracted and formatted code string, or None if processing fails
    """
    return _get_code_processor().process_code_with_llm(element, json_file_path)
