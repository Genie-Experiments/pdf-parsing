# PDF Parsing Pipeline with Dolphin AI Model

A comprehensive PDF document parsing pipeline that uses ByteDance's Dolphin AI model to extract and process various document elements including tables, code blocks, and figures from PDF files.
## 🌟 Features

- **Batch PDF Processing**: Process multiple PDF files in a directory simultaneously
- **AI-Powered Document Analysis**: Uses Dolphin model for intelligent document layout understanding
- **LLM-Enhanced Code Processing**: Optional high-quality code extraction using OpenAI GPT-4o Vision API
- **Intelligent Section Hierarchy Fixing**: Automatically corrects markdown heading levels using TOC JSON structure matching
- **Structured Output**: Generates organized JSON and Markdown outputs for each processed document

## 📋 Prerequisites

- Python 3.10 or higher
- Windows, macOS, or Linux
- CUDA-compatible GPU (recommended for faster processing)

## 🚀 Installation

Follow these steps to properly set up the repository:

### 1. Clone the Repository

```bash
git clone https://github.com/Genie-Experiments/pdf-parsing.git
```
```bash
cd pdf-parsing
```
### 2. Initialize Submodules

```bash
git submodule update --init
```

### 3. Install Dependencies

```bash
uv sync
```

### 4. Activate Virtual Environment

```bash
source .venv/bin/activate
```

### 5. Download the Dolphin Model

```bash
cd Dolphin
huggingface-cli download ByteDance/Dolphin-1.5 --local-dir ./hf_model
cd ..
```

### 6. Configure Environment Variables

create a `.env` file in the project's root directory and copy the below content in the `.env` file then adjust the settings accordingly:

```

#### .env File Structure

```env
# Directory paths
DATA_DIRECTORY=./data # Directory where your PDFs are stored
OUTPUT_DIRECTORY=./results # Directory for storing output results
PROCESSED_IMAGES_DIR=./processed_images_by_dolphin # Directory for storing processed images by dolphin
RAW_PDF_TEXT_DIR=./raw_pdf_text # Directory for storing raw PDF text
HIERARCHY_JSON_DIRECTORY=./section_hierarchy_pdfs # Directory for storing section hierarchy JSON files

# !! Important: Internal paths: Do not change these values !!
DOLPHIN_SCRIPT=./Dolphin/demo_page.py
MODEL_PATH=./Dolphin/hf_model
HTML_TO_MARKDOWN_DIR=./html-to-markdown

# Processing flags
PROCESS_CODE_USING_LLM=false # Whether to use LLM for code segments refinement
PROCESS_FIGURES_USING_LLM=false # Whether to use LLM for generating figures description
SEGMENTS_TO_REFINE=["code","fig","tab"] 
# Comma-separated list of segment types to refine: Supported: code, fig, tab. By refinement we mean that for tables, html code will be converted to clean markdown. For code, existing code segments in markdown will be replaced with well formatted code segments. For figures, if PROCESS_FIGURES_USING_LLM=True the figures will be sent to LLM for description generation. 

# OpenAI models
#OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL_VISION=gpt-4o-mini # Model for code segments refinement
OPENAI_MODEL_TEXT=gpt-4o-mini # Model for generating figure descriptions

# Limits
MAX_CONTEXT_LENGTH=5000
MAX_DESCRIPTION_LENGTH=1000

# Logging
DEFAULT_LOG_LEVEL=INFO
```

Required environment variables:
- `OPENAI_API_KEY`: Your OpenAI API key (required only if using LLM processing)

### 8. Run the Pipeline

```bash
python main.py
```

## 🔧 How the Project Works

### Processing Pipeline Steps

The pipeline automatically executes the following steps in sequence:

#### Step 1: Initial PDF Processing
- **Process PDF files** using the Dolphin AI model to extract baseline markdown
- Converts PDFs to structured markdown with layout analysis
- Creates JSON files containing document structure and element coordinates

#### Step 2: Raw Text Extraction
- **Extract raw text** from all PDF files using PyMuPDF
- Stores clean text in `RAW_PDF_TEXT_DIR` for later OCR error correction
- Maintains original document structure and formatting

#### Step 3: Section Hierarchy Generation
- **Generate section hierarchy JSONs** from PDFs by analyzing text formatting
- Detects headings based on font size, bold formatting, and structure
- Creates TOC (Table of Contents) structure for later markdown heading correction

#### Step 4: Backup Creation
- **Create backup** of all markdown files before post-processing
- Adds `_backup` suffix to preserve original processed files
- Ensures data safety during intensive post-processing operations

#### Step 5: Segment Refinement
- **Process JSON files** for segment refinement based on `SEGMENTS_TO_REFINE` configuration
- Refines specific document elements (code blocks, figures, tables)
- Optionally uses LLM processing for enhanced code and figure extraction

#### Step 6: Page Break Insertion
- **Insert page breaks** in markdown files to maintain document structure
- Adds clear separators between pages for better readability
- Preserves original document pagination context

#### Step 7: Header and Footer Removal
- **Remove headers and footers** from markdown files
- Cleans up repetitive content that appears on every page
- Improves content quality by removing non-essential document elements

#### Step 8: OCR Error Correction
- **Fix OCR errors** by comparing processed markdown with raw PDF text
- Uses fuzzy string matching to identify and correct OCR mistakes
- Leverages clean raw text extraction to improve accuracy
- Preserves document structure while enhancing text quality

#### Step 9: Section Hierarchy Correction
- **Fix markdown section hierarchy** using the generated hierarchy JSON files
- Corrects heading levels (number of `#` characters) based on document structure
- Ensures proper markdown heading organization and navigation
- Matches sections across different document formats for consistency

#### Step 10: Bullet Point Standardization
- **Standardize bullet point formatting** in markdown files
- Converts inconsistent bullet symbols (•, ◦) to standard markdown format (-)
- Fixes mixed bullet and numbered list formatting
- Standardizes numbered lists by ensuring proper formatting (e.g., "1.", "2.")
- Handles various bullet point patterns:
  - Converts "- •" to "-"
  - Converts "- ◦" to "-"
  - Fixes "- number." to "number." for numbered lists
  - Converts standalone "•" or "◦" to "-"
  - Standardizes numbered list formats

## 📊 Output Formats

### JSON Output (`doc_name.json`)
Contains the complete document structure with:
- Page-by-page layout analysis
- Element bounding boxes and coordinates
- Text content for each element
- Element types and reading order

### Markdown Output (`.md` files)
- Clean, readable Markdown format
- Properly formatted tables
- Preserved document structure
- Easy to integrate with documentation workflows

### Figures (`.png` files)
- Figures present in the pdf document are stored in the output directory you specified 
  in the config file. Example path: `output_dir/doc_name/markdown/figures/figure-1.png` 

## 📄 License

This project incorporates ByteDance's Dolphin model. Please refer to the original Dolphin repository for licensing information: [ByteDance/Dolphin](https://github.com/bytedance/Dolphin)

## 🙏 Acknowledgments

- [ByteDance Dolphin](https://github.com/bytedance/Dolphin) - The core AI model for document parsing
- [Html to Markdown converter](https://github.com/JohannesKaufmann/html-to-markdown) - The HTML to Markdown converter for clean table formatting