"""
Figure Processing Module for PDF Parsing Pipeline

This module handles the extraction and processing of figures from PDF documents,
including context gathering, AI-powered description generation, and markdown integration.

Features:
- Extract figure information and surrounding context
- Generate descriptions using OpenAI Vision API
- Fallback to context-based description generation
- Integration with markdown files

Author: PDF Parsing Pipeline
Date: September 2025
"""

import os
import json
import base64
from pathlib import Path
from typing import Dict, List, Optional, Any
import openai
from dotenv import load_dotenv
from utils.get_markdown_file_path import get_markdown_file_path
from utils.logger import get_logger, log_success, log_error, log_warning

# Load environment variables
load_dotenv()

# Configure logging
logger = get_logger(__name__)

# Constants
MAX_CONTEXT_LENGTH = 5000
MAX_DESCRIPTION_LENGTH = 1000
VISION_MODEL = "gpt-4o-mini"
TEXT_MODEL = "gpt-4o-mini"
SUPPORTED_IMAGE_FORMATS = ['.png', '.jpg', '.jpeg', '.gif', '.bmp']


class FigureProcessor:
    """
    Main class for processing figures in PDF documents.
    
    This class handles the complete workflow of figure processing including:
    - Context extraction
    - AI-powered description generation
    - Markdown integration
    """
    
    def __init__(self):
        """Initialize the FigureProcessor with API configuration."""
        self.openai_client = None
        self._initialize_openai_client()
    
    def _initialize_openai_client(self) -> None:
        """Initialize OpenAI client if API key is available."""
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            try:
                self.openai_client = openai.OpenAI(api_key=api_key)
                logger.info("OpenAI client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self.openai_client = None
        else:
            logger.warning("OpenAI API key not found in environment variables")
    
    def extract_figure_info_and_context(
        self, 
        element: Dict[str, Any], 
        page_elements: List[Dict[str, Any]], 
        json_file_path: str
    ) -> Dict[str, Any]:
        """
        Extract comprehensive figure information and surrounding context.
        
        Args:
            element: The figure element from JSON recognition data
            page_elements: All elements from the current page
            json_file_path: Path to the JSON file
            
        Returns:
            Dictionary containing figure information:
            - figure_path: Absolute path to the figure image
            - relative_figure_path: Relative path for markdown
            - image_exists: Boolean indicating if image file exists
            - context_text: Surrounding text context
            - figure_text: Original figure text/reference
            - metadata: Additional figure metadata
        """
        try:
            # Extract basic figure information
            figure_path = element.get("figure_path", "")
            text = element.get("text", "")
            
            # Extract figure path from markdown reference if not directly available
            if not figure_path and "![Figure]" in text:
                figure_path = self._extract_figure_path_from_text(text)
            
            # Resolve absolute image path
            full_image_path = self._resolve_image_path(figure_path, json_file_path)
            
            # Validate image file
            image_exists = self._validate_image_file(full_image_path)
            
            # Gather contextual information
            context_text = self._gather_section_context(element, page_elements)
            
            # Extract metadata
            metadata = self._extract_figure_metadata(element)
            
            return {
                "figure_path": str(full_image_path) if image_exists else "",
                "relative_figure_path": figure_path,
                "image_exists": image_exists,
                "context_text": context_text,
                "figure_text": text,
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Error extracting figure info: {e}")
            return self._get_empty_figure_info()
    
    def _extract_figure_path_from_text(self, text: str) -> str:
        """Extract figure path from markdown-style image reference."""
        import re
        match = re.search(r'!\[Figure\]\(([^)]+)\)', text)
        return match.group(1) if match else ""
    
    def _resolve_image_path(self, figure_path: str, json_file_path: str) -> Path:
        """Convert relative figure path to absolute path."""
        json_path = Path(json_file_path)
        base_dir = json_path.parent.parent  # Go up two levels from recognition_json
        return base_dir / "markdown" / figure_path
    
    def _validate_image_file(self, image_path: Path) -> bool:
        """Validate that the image file exists and has supported format."""
        if not image_path.exists():
            return False
        
        suffix = image_path.suffix.lower()
        return suffix in SUPPORTED_IMAGE_FORMATS
    
    def _extract_figure_metadata(self, element: Dict[str, Any]) -> Dict[str, Any]:
        """Extract additional metadata from figure element."""
        return {
            "bbox": element.get("bbox", []),
            "reading_order": element.get("reading_order"),
            "label": element.get("label", "fig"),
            "confidence": element.get("confidence"),
            "page_number": element.get("page_number")
        }
    
    def _get_empty_figure_info(self) -> Dict[str, Any]:
        """Return empty figure info structure for error cases."""
        return {
            "figure_path": "",
            "relative_figure_path": "",
            "image_exists": False,
            "context_text": "",
            "figure_text": "",
            "metadata": {}
        }


    def _gather_section_context(
        self, 
        figure_element: Dict[str, Any], 
        page_elements: List[Dict[str, Any]]
    ) -> str:
        """
        Gather comprehensive text context from the section containing the figure.
        
        Args:
            figure_element: The figure element
            page_elements: All elements from the page
            
        Returns:
            Contextual text from the document section
        """
        try:
            figure_reading_order = figure_element.get("reading_order", 0)
            
            # Sort elements by reading order for proper sequence
            sorted_elements = sorted(
                page_elements, 
                key=lambda x: x.get("reading_order", 0)
            )
            
            # Find section boundaries
            section_start_idx = self._find_section_start(
                sorted_elements, figure_reading_order
            )
            section_end_idx = self._find_section_end(
                sorted_elements, figure_reading_order
            )
            
            # Extract and clean text from the section
            context_parts = self._extract_section_text(
                sorted_elements, section_start_idx, section_end_idx
            )
            
            # Join and truncate if necessary
            context_text = "\n\n".join(context_parts)
            
            if len(context_text) > MAX_CONTEXT_LENGTH:
                context_text = context_text[:MAX_CONTEXT_LENGTH] + "..."
                logger.info(f"Context truncated to {MAX_CONTEXT_LENGTH} characters")
            
            return context_text
            
        except Exception as e:
            logger.error(f"Error gathering section context: {e}")
            return ""
    
    def _find_section_start(
        self, 
        sorted_elements: List[Dict[str, Any]], 
        figure_reading_order: int
    ) -> int:
        """Find the start index of the section containing the figure."""
        section_labels = ["sec", "sub_sec", "sub_sub_sec", "header", "title"]
        section_start_idx = 0
        
        for i, elem in enumerate(sorted_elements):
            if elem.get("reading_order", 0) >= figure_reading_order:
                break
            if elem.get("label") in section_labels:
                section_start_idx = i
        
        return section_start_idx
    
    def _find_section_end(
        self, 
        sorted_elements: List[Dict[str, Any]], 
        figure_reading_order: int
    ) -> int:
        """Find the end index of the section containing the figure."""
        section_labels = ["sec", "sub_sec", "sub_sub_sec"]
        
        for i, elem in enumerate(sorted_elements):
            if (elem.get("reading_order", 0) > figure_reading_order and 
                elem.get("label") in section_labels):
                return i
        
        return len(sorted_elements)
    
    def _extract_section_text(
        self, 
        sorted_elements: List[Dict[str, Any]], 
        start_idx: int, 
        end_idx: int
    ) -> List[str]:
        """Extract and clean text from section elements."""
        context_parts = []
        excluded_labels = ["fig", "watermark", "page_header", "page_footer"]
        
        for i in range(start_idx, end_idx):
            elem = sorted_elements[i]
            
            if elem.get("label") not in excluded_labels:
                text = elem.get("text", "").strip()
                if text and len(text) > 3:  # Filter out very short text
                    context_parts.append(text)
        
        return context_parts


class VisionDescriptionGenerator:
    """Handles AI-powered figure description generation using vision models."""
    
    def __init__(self, openai_client: Optional[openai.OpenAI] = None):
        """
        Initialize the vision description generator.
        
        Args:
            openai_client: Optional pre-initialized OpenAI client
        """
        self.client = openai_client
    
    def generate_vision_description(
        self, 
        figure_path: str, 
        context_text: str
    ) -> Optional[str]:
        """
        Generate figure description using OpenAI Vision API.
        
        Args:
            figure_path: Path to the figure image file
            context_text: Surrounding document context
            
        Returns:
            Generated description or None if failed
        """
        if not self.client:
            logger.error("OpenAI client not available for vision analysis")
            return None
        
        try:
            # Load and encode image
            base64_image = self._encode_image_to_base64(figure_path)
            if not base64_image:
                return None
            
            # Create vision prompt
            prompt = self._create_vision_prompt(context_text)
            
            # Call OpenAI Vision API
            response = self._call_vision_api(prompt, base64_image)
            
            if response:
                logger.info("Successfully generated vision-based description")
                log_success("Generated description using OpenAI Vision (actual image analysis)")
                return response
            
            return None
            
        except Exception as e:
            logger.error(f"Vision description generation failed: {e}")
            log_warning(f"OpenAI Vision failed: {str(e)}")
            return None
    
    def _encode_image_to_base64(self, figure_path: str) -> Optional[str]:
        """Encode image file to base64 string."""
        try:
            with open(figure_path, 'rb') as img_file:
                image_data = img_file.read()
                return base64.b64encode(image_data).decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to encode image {figure_path}: {e}")
            return None
    
    def _create_vision_prompt(self, context_text: str) -> str:
        """Create comprehensive prompt for vision analysis."""
        return f"""You are an expert technical documentation analyst. Analyze the provided figure/image and generate a comprehensive description.

Context from surrounding document: {context_text}

Please provide a detailed description following this structure:

**Figure Description:**
[Provide the main description of what the figure shows - be specific about what you can actually see]

**Relationship to the surrounding context:**
[Explain how this figure relates to the context provided]

**Technical details:**
[Describe technical elements, metrics, data, UI elements, graphs, etc. that are visible]

**Key components or elements:**
[List and describe the key visual elements you can see in the image]

**Purpose and significance:**
[Explain the purpose and importance of this figure]

Focus on describing what you can actually see in the image rather than making assumptions based on context alone. Be specific about UI elements, buttons, graphs, diagrams, text visible in the image, etc."""
    
    def _call_vision_api(self, prompt: str, base64_image: str) -> Optional[str]:
        """Make API call to OpenAI Vision model."""
        try:
            response = self.client.chat.completions.create(
                model=VISION_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.3,
                max_tokens=MAX_DESCRIPTION_LENGTH
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Vision API call failed: {e}")
            return None


class ContextDescriptionGenerator:
    """Handles context-based figure description generation as fallback method."""
    
    def __init__(self, openai_client: Optional[openai.OpenAI] = None):
        """
        Initialize the context description generator.
        
        Args:
            openai_client: Optional pre-initialized OpenAI client
        """
        self.client = openai_client
    
    def generate_context_description(
        self, 
        figure_path: str, 
        context_text: str
    ) -> Optional[str]:
        """
        Generate figure description based on surrounding context only.
        
        Args:
            figure_path: Path to the figure image file
            context_text: Surrounding document context
            
        Returns:
            Generated description or None if failed
        """
        if not self.client:
            logger.error("OpenAI client not available for context-based analysis")
            log_error("OpenAI API key not configured. Cannot generate description.")
            return None
        
        try:
            # Create context-based prompt
            prompt = self._create_context_prompt(figure_path, context_text)
            
            # Call OpenAI text API
            response = self._call_text_api(prompt)
            
            if response:
                logger.info("Successfully generated context-based description")
                log_success("Generated description using OpenAI context-based approach (text only)")
                return response
            
            return None
            
        except Exception as e:
            logger.error(f"Context description generation failed: {e}")
            log_error(f"Error generating figure description: {str(e)}")
            return None
    
    def _create_context_prompt(self, figure_path: str, context_text: str) -> str:
        """Create prompt for context-based description generation."""
        return f"""You are an expert technical documentation analyst. Based on the surrounding context, generate a professional description for a figure in technical documentation.

Context from the document section:
{context_text}

Figure file name: {os.path.basename(figure_path)}

Please provide a comprehensive description of what the figure likely shows based on the context. Include:
1. What type of figure it likely is (diagram, chart, screenshot, network topology, etc.)
2. How it relates to the surrounding context
3. Technical details that would be important for understanding
4. Key components or elements that would typically be shown
5. The purpose and significance of this figure in the documentation

Keep the description professional, technical, and detailed. Write it as if you're describing the figure to someone who cannot see it but needs to understand what it depicts and its relevance to the technical content.

Figure Description:
"""
    
    def _call_text_api(self, prompt: str) -> Optional[str]:
        """Make API call to OpenAI text model."""
        try:
            response = self.client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=MAX_DESCRIPTION_LENGTH // 2,  # Shorter for context-based
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Text API call failed: {e}")
            return None


class FigureDescriptionManager:
    """
    Coordinated manager for figure description generation.
    
    This class orchestrates the complete description generation workflow,
    trying vision-based analysis first and falling back to context-based
    generation when necessary.
    """
    
    def __init__(self):
        """Initialize the description manager with AI generators."""
        self.openai_client = self._get_openai_client()
        self.vision_generator = VisionDescriptionGenerator(self.openai_client)
        self.context_generator = ContextDescriptionGenerator(self.openai_client)
    
    def _get_openai_client(self) -> Optional[openai.OpenAI]:
        """Get OpenAI client if API key is available."""
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            try:
                return openai.OpenAI(api_key=api_key)
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
        return None
    
    def generate_description(
        self, 
        figure_path: str, 
        context_text: str
    ) -> Optional[str]:
        """
        Generate the best possible figure description.
        
        Attempts vision-based analysis first, then falls back to context-based
        generation if vision analysis fails.
        
        Args:
            figure_path: Path to the figure image file
            context_text: Surrounding document context
            
        Returns:
            Generated description or None if all methods failed
        """
        if not self.openai_client:
            logger.error("No OpenAI client available for description generation")
            log_error("OpenAI API key not configured. Cannot generate description.")
            return None
        
        # Strategy 1: Try vision-based analysis (most accurate)
        if Path(figure_path).exists():
            description = self.vision_generator.generate_vision_description(
                figure_path, context_text
            )
            if description:
                return description
        
        # Strategy 2: Fall back to context-based analysis
        logger.info("Falling back to context-based description generation")
        logger.info("Using context-based description (vision analysis failed or unavailable)")
        
        return self.context_generator.generate_context_description(
            figure_path, context_text
        )


# Backward compatibility functions
def generate_figure_description(figure_path: str, context_text: str) -> Optional[str]:
    """
    Legacy function for backward compatibility.
    
    Args:
        figure_path: Path to the figure image
        context_text: Surrounding context text
        
    Returns:
        Generated figure description or None if failed
    """
    manager = FigureDescriptionManager()
    return manager.generate_description(figure_path, context_text)





class MarkdownIntegrator:
    """Handles integration of figure descriptions into markdown files."""
    
    def search_and_replace_figure(
        self, 
        figure_text: str, 
        description: str, 
        json_file_path: str
    ) -> bool:
        """
        Search for figure text in markdown and replace with AI-generated description.
        
        Args:
            figure_text: Original figure text/reference from JSON
            description: AI-generated figure description
            json_file_path: Path to the JSON file for markdown path resolution
            
        Returns:
            True if replacement was successful, False otherwise
        """
        try:
            # Get corresponding markdown file path
            markdown_path = get_markdown_file_path(json_file_path)
            
            if not markdown_path.exists():
                logger.error(f"Markdown file not found: {markdown_path}")
                log_error(f"Markdown file not found: {markdown_path}")
                return False
            
            # Read current markdown content
            original_content = self._read_markdown_file(markdown_path)
            if original_content is None:
                return False
            
            # Perform replacement
            updated_content = self._replace_figure_text(
                original_content, figure_text, description
            )
            
            if updated_content == original_content:
                logger.warning("Figure text not found in markdown file")
                log_error("Figure text not found in markdown file")
                return False
            
            # Write updated content back
            return self._write_markdown_file(markdown_path, updated_content)
            
        except Exception as e:
            logger.error(f"Error replacing figure in markdown: {e}")
            log_error(f"Error replacing figure in markdown: {str(e)}")
            return False
    
    def _read_markdown_file(self, markdown_path: Path) -> Optional[str]:
        """Safely read markdown file content."""
        try:
            with open(markdown_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read markdown file {markdown_path}: {e}")
            return None
    
    def _replace_figure_text(
        self, 
        content: str, 
        figure_text: str, 
        description: str
    ) -> str:
        """Replace figure text with description in content."""
        figure_text_clean = figure_text.strip()
        if figure_text_clean in content:
            return content.replace(figure_text_clean, description)
        return content
    
    def _write_markdown_file(self, markdown_path: Path, content: str) -> bool:
        """Safely write content to markdown file."""
        try:
            with open(markdown_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Successfully updated markdown file: {markdown_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to write markdown file {markdown_path}: {e}")
            return False


# Main processing function
def process_figure_element(
    element: Dict[str, Any], 
    page_elements: List[Dict[str, Any]], 
    json_file_path: str
) -> bool:
    """
    Process a single figure element through the complete workflow.
    
    This is the main entry point for figure processing, coordinating:
    1. Figure information extraction
    2. Context gathering
    3. AI-powered description generation
    4. Markdown file integration
    
    Args:
        element: The figure element from JSON recognition data
        page_elements: All elements from the current page
        json_file_path: Path to the JSON file
        
    Returns:
        True if processing was successful, False otherwise
    """
    try:
        logger.info("Found FIG:")
        
        # Initialize processors
        figure_processor = FigureProcessor()
        description_manager = FigureDescriptionManager()
        markdown_integrator = MarkdownIntegrator()
        
        # Extract figure information and context
        info = figure_processor.extract_figure_info_and_context(
            element, page_elements, json_file_path
        )
        
        # Display figure metadata
        _display_figure_metadata(info)
        
        # Validate figure
        if not info["image_exists"]:
            log_error(f"Figure image not found: {info['relative_figure_path']}")
            return False
        
        logger.info("Extracting figure information and context...")
        log_success(f"Figure image found: {info['relative_figure_path']}")
        logger.info(f"Context length: {len(info['context_text'])} characters")
        
        # Generate AI description
        logger.info("Generating figure description using AI...")
        
        description = description_manager.generate_description(
            info["figure_path"], info["context_text"]
        )
        
        if not description:
            log_error("Failed to generate figure description")
            return False
        
        # Display generated description
        _display_generated_description(description)
        
        # Integrate with markdown
        logger.info("Replacing figure text with description in markdown...")
        success = markdown_integrator.search_and_replace_figure(
            info["figure_text"], description, json_file_path
        )
        
        if success:
            log_success("Figure text successfully replaced with description!")
        else:
            log_error("Failed to replace figure text with description")
        
        return success
        
    except Exception as e:
        logger.error(f"Error processing figure element: {e}")
        log_error(f"Error processing figure: {str(e)}")
        return False


def _display_figure_metadata(info: Dict[str, Any]) -> None:
    """Display figure metadata for logging purposes."""
    metadata = info.get("metadata", {})
    
    bbox = metadata.get("bbox", [])
    if bbox:
        logger.info(f"Bounding Box: {bbox}")
    
    reading_order = metadata.get("reading_order")
    if reading_order is not None:
        logger.info(f"Reading Order: {reading_order}")
    
    figure_text = info.get("figure_text", "")
    if figure_text:
        logger.info("Figure Text/Reference:")
        logger.info(f"{figure_text}")


def _display_generated_description(description: str) -> None:
    """Display the generated description for logging purposes."""
    logger.info("Generated Description:")
    logger.info("----------------------------------------")
    logger.info(f"{description}")
    logger.info("----------------------------------------")


# Backward compatibility functions
def get_figure_info_and_context(
    element: Dict[str, Any], 
    page_elements: List[Dict[str, Any]], 
    json_file_path: str
) -> Dict[str, Any]:
    """Legacy function for backward compatibility."""
    processor = FigureProcessor()
    return processor.extract_figure_info_and_context(element, page_elements, json_file_path)


def search_and_replace_figure_in_markdown(
    figure_text: str, 
    description: str, 
    json_file_path: str
) -> bool:
    """Legacy function for backward compatibility."""
    integrator = MarkdownIntegrator()
    return integrator.search_and_replace_figure(figure_text, description, json_file_path)