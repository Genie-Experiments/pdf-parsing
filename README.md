# PDF Parsing Pipeline with Dolphin AI Model

A comprehensive PDF document parsing pipeline that uses ByteDance's Dolphin AI model to extract and process various document elements including tables, code blocks, and figures from PDF files. For the tables only, the extracted HTML tables are converted to clean Markdown format for better readability and processing using html-to-markdown repository.
## 🌟 Features

- **Batch PDF Processing**: Process multiple PDF files in a directory simultaneously
- **AI-Powered Document Analysis**: Uses Dolphin model for intelligent document layout understanding
- **HTML to Markdown Conversion**: Automatically converts extracted HTML tables(by Dolphin) to clean Markdown format
- **LLM-Enhanced Code Processing**: Optional high-quality code extraction using OpenAI GPT-4o Vision API
- **Structured Output**: Generates organized JSON and Markdown outputs for each processed document

## 📋 Prerequisites

- Python 3.10 or higher
- Windows, macOS, or Linux
- CUDA-compatible GPU (recommended for faster processing)
- Git LFS (for downloading model files)

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Genie-Experiments/pdf-parsing.git
cd pdf-parsing-pipeline
```

### 2. Install Dependencies

Install the required Python packages:

```bash
# Install main project dependencies
pip install -e .

# Install Dolphin model dependencies
pip install -r Dolphin/requirements.txt
```

The main dependencies include:
- `torch` and `torchvision` (PyTorch framework)
- `transformers` (Hugging Face transformers)
- `pillow` (Image processing)
- `pymupdf` (PDF processing)
- `opencv-python` (Computer vision)
- `openai` (For LLM-based code processing)
- `python-dotenv` (Environment variables)
- And other supporting libraries

### 3. Configure Environment Variables (Optional)

For LLM-based code processing, create a `.env` file:

```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
```

Required environment variables:
- `OPENAI_API_KEY`: Your OpenAI API key (required only if using LLM code processing)

### 3. Download the Dolphin Model

You have two options for downloading the pre-trained Dolphin model:

**Option A: Download from Hugging Face (Recommended)**

```bash
cd Dolphin
git lfs install
git clone https://huggingface.co/ByteDance/Dolphin ./hf_model
```

**Option B: Using Hugging Face CLI**

```bash
cd Dolphin
pip install huggingface_hub
huggingface-cli download ByteDance/Dolphin --local-dir ./hf_model
```

### 4. Build HTML to Markdown Converter (Optional)

If you need to rebuild the HTML to Markdown converter:

```bash
cd html-to-markdown
go build -o html2markdown.exe
```

## ⚙️ Configuration

Before running the pipeline, you may need to adjust the configuration in `main.py`:

```python
# Define paths
DATA_DIRECTORY = "./test-data"        # Directory containing PDF files to process
OUTPUT_DIRECTORY = "./results"        # Directory for output results
DOLPHIN_SCRIPT = "./Dolphin/demo_page_hf.py"  # Dolphin inference script
MODEL_PATH = "./Dolphin/hf_model"     # Path to downloaded Dolphin model

# Configuration flags
PROCESS_CODE_USING_LLM = False        # Enable LLM-based code processing (requires OpenAI API key)
SEGMENTS_TO_EXTRACT = ["tab", "code"] # Types of segments to extract and process
```

### Configuration Options:

- **DATA_DIRECTORY**: Path to the folder containing PDF files you want to process
- **OUTPUT_DIRECTORY**: Path where processed results will be saved
- **MODEL_PATH**: Path to the Dolphin model (should match where you downloaded it)
- **PROCESS_CODE_USING_LLM**: Enable high-quality code extraction using OpenAI GPT-4o Vision API
- **SEGMENTS_TO_EXTRACT**: List of segment types to extract (supported: "tab", "code", "fig")

### LLM Code Processing Feature

When `PROCESS_CODE_USING_LLM=True`, the pipeline will:
1. **Detect code blocks** using the Dolphin model
2. **Extract bounding box coordinates** for each code block
3. **Locate the corresponding page image** in `Processed-Images-By-Dolphin/`
4. **Crop the code section** from the page image
5. **Send the cropped image** to OpenAI GPT-4o Vision API
6. **Extract and format code** with high accuracy
7. **Replace original text** with the LLM-processed code in Markdown files

This feature provides significantly better code extraction quality compared to traditional OCR methods, especially for complex code with special characters, indentation, and formatting.
## 📁 Project Structure

```
pdf-parsing-pipeline/
├── main.py                           # Main pipeline orchestrator
├── process_pdf_files.py              # PDF processing logic
├── process_json_files.py             # JSON results processing
├── extract_segments.py               # Document segment extraction
├── convert_html_to_markdown.py       # HTML to Markdown conversion
├── replace_html_with_markdown.py     # HTML replacement utilities
├── test-data/                        # Sample PDF files
│   ├── *.pdf                        # Your PDF files go here
├── results/                          # Processing outputs
│   └── [pdf-name]/                   # Individual PDF results
│       ├── recognition.json          # Structured document data
│       └── *.md                      # Markdown outputs
├── Dolphin/                          # ByteDance Dolphin AI model
│   ├── demo_page_hf.py              # Hugging Face inference script
│   ├── hf_model/                     # Downloaded model files
│   ├── requirements.txt              # Python dependencies
│   └── utils/                        # Utility functions
└── html-to-markdown/                 # HTML to Markdown converter
    └── html2markdown.exe             # Converter executable
```

## 🏃‍♂️ Usage

### 1. Prepare Your PDF Files

Place the PDF files you want to process in the `test-data` directory:

```bash
cp your-document.pdf ./test-data/
```

### 2. Run the Pipeline

Execute the main pipeline script:

```bash
python main.py
```

### 3. Processing Steps

The pipeline will automatically:

1. **Scan** the `test-data` directory for PDF files
2. **Create** individual output directories for each PDF in `results/`
3. **Process** each PDF using the Dolphin AI model
4. **Extract** specified document segments (tables, code, figures)
5. **Convert** HTML tables to clean Markdown format
6. **Save** structured results in JSON and Markdown formats

### 4. Check Results

After processing, check the `results` directory:

```
results/
└── your-document/
    ├── recognition.json      # Complete document structure
    ├── page_1.md            # Markdown for page 1
    ├── page_2.md            # Markdown for page 2
    └── ...
```

## 📊 Output Formats

### JSON Output (`recognition.json`)
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

## 🐛 Troubleshooting

### Common Issues:

1. **CUDA Out of Memory**: If you encounter GPU memory issues, the model will automatically fall back to CPU processing.

2. **Model Download Fails**: Ensure you have `git lfs` installed and sufficient disk space (~2-3GB for the model).

3. **HTML Converter Not Found**: Make sure `html2markdown.exe` exists in the `html-to-markdown` directory.

4. **No PDFs Found**: Verify that your PDF files are in the correct directory and have `.pdf` extension.

### Getting Help:

- Check the console output for detailed error messages
- Ensure all dependencies are properly installed
- Verify that the Dolphin model is correctly downloaded

## 📄 License

This project incorporates ByteDance's Dolphin model. Please refer to the original Dolphin repository for licensing information: [ByteDance/Dolphin](https://github.com/bytedance/Dolphin)

## 🙏 Acknowledgments

- [ByteDance Dolphin](https://github.com/bytedance/Dolphin) - The core AI model for document parsing
- [Html to Markdown converter](https://github.com/JohannesKaufmann/html-to-markdown) - The HTML to Markdown converter for clean table formatting