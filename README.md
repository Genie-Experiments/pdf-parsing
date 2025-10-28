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

### 6. Configure Settings

Set the directory paths and settings in the config file: `pdf-parsing/config/config.py`

Required configuration options:
- `DATA_DIRECTORY`: Directory containing PDF files to process
- `OUTPUT_DIRECTORY`: Directory for output results
- `PROCESSED_IMAGES_DIR`: Directory to save processed images by Dolphin
- `RAW_PDF_TEXT_DIR`: Directory to store raw extracted PDF texts
- `HIERARCHY_JSON_DIRECTORY`: Directory to store pdf's section hierarchy
- `PROCESS_CODE_USING_LLM`: Enable LLM-based code processing (requires OpenAI API key)
- `PROCESS_FIGURES_USING_LLM`: Enable LLM-based figure processing (requires OpenAI API key)
- `SEGMENTS_TO_REFINE`: Types of segments to refine (supported: "code", "fig", "tab")

### 7. Configure Environment Variables (Optional)

For LLM-based processing, create a `.env` file:

```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
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
- Configurable parameters:
  - `min_heading_size`: Minimum font size for headings (default: 12)
  - `max_levels`: Maximum heading depth (default: 6)
  - `exclude_headers_footers`: Remove headers/footers from hierarchy analysis

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