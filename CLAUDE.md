# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

- Python 3.12, dependencies managed with `uv` (use `uv add` not `pip install`)
- Two git submodules: `Dolphin/` (ByteDance PDF model) and `html-to-markdown/` (Go binaries for table conversion)
- All config via Pydantic `BaseSettings` in `config/config.py` — overridable through `.env` or environment variables
- `DATA_DIRECTORY` and `OUTPUT_DIRECTORY` are the two required env vars; `OPENAI_API_KEY` only needed if LLM refinement is enabled

## Running the Pipeline

```bash
python main.py   # Run all 10 post-processing steps sequentially
```

No automated tests. `evaluation_scripts/` contains standalone validation tools:
- `compare_text.py` — character/word-level OCR accuracy comparison
- `sections_accuracy_comparison.py` — heading hierarchy accuracy vs ground truth
- `extract_hierarchy_md.py` — helper for parsing markdown hierarchy

## Architecture

### Data Flow

```
Raw PDFs → [Dolphin model] → JSON + Markdown + Images
         → [Post-processing steps 2–10] → Clean Markdown
```

The pipeline preserves directory structure from `DATA_DIR` into `OUTPUT_DIR` throughout all steps. All post-processing steps recursively walk `OUTPUT_DIR` using `rglob()`.

### 10-Step Pipeline (`main.py`)

1. **Process PDFs** — spawns Dolphin as a subprocess (`Dolphin/demo_page.py`) to produce `.json` + `.md` + images per PDF
2. **Extract raw text** — PyMuPDF extraction saved as `.txt`, used later as OCR correction reference
3. **Generate section hierarchy JSONs** — analyzes PDF font metrics to detect heading levels
4. **Create backups** — copies `.md` files with `_backup` suffix before any mutation
5. **Process JSON files** — dispatches segment refinement per JSON element (see below)
6. **Insert page breaks** — replaces `---` markers with `<!-- page_break_N -->` HTML comments
7. **Remove headers/footers** — detects and removes repetitive cross-page content
8. **Fix OCR errors** — fuzzy-matches markdown text against raw PyMuPDF text to correct OCR mistakes
9. **Fix markdown section hierarchy** — corrects heading levels using the hierarchy JSON from step 3
10. **Standardize bullet points** — converts `•`, `◦`, etc. to standard markdown `-`

Steps 3 and 9 are tightly coupled: step 3 writes a hierarchy JSON, step 9 reads it.

### Segment Refinement (`post_processing/refine_segments.py`)

Dolphin labels each JSON element as `"tab"`, `"code"`, `"fig"`, or `"catalogue"`:
- **`"tab"`** → HTML-to-Markdown via `html-to-markdown` submodule (platform-specific Go binary)
- **`"code"`** → bounding-box crop from PDF → always cleaned via `clean_and_format_code.py`; `PROCESS_CODE_USING_LLM=true` adds GPT-4o Vision on top
- **`"fig"`** → GPT-4o Vision description; skipped entirely if `PROCESS_FIGURES_USING_LLM=false`
- **`"catalogue"`** → removes the matching text from the markdown (cleanup only)

### Configuration (`config/config.py`)

Key settings:
- `SEGMENTS_TO_REFINE` — which segment types to process (default: `["tab", "code", "fig"]`; also accepts `"catalogue"`)
- `OPENAI_VISION_MODEL`, `OPENAI_TEXT_MODEL` — default: `gpt-4o-mini`
- `PROCESS_CODE_USING_LLM`, `PROCESS_FIGURES_USING_LLM` — toggle LLM enhancement (default: off)

### Logging (`utils/logger.py`)

Singleton logger. Use these convenience functions — do not use `print` or `logging` directly:
```python
from utils.logger import log_step, log_success, log_error, log_warning, log_processing_stats
```
Logs to console (colored) and `logs/pdf_parsing.log` (rotating, 10 MB max, 5 backups).

### Key Path Utilities

These form a bidirectional path mapping system used throughout post-processing:
- `utils/get_markdown_file_path.py` — resolves a JSON path to its corresponding `.md` file
- `utils/get_pdf_file_path.py` — resolves an output path back to the source PDF in `DATA_DIR`
- `utils/image_cropping.py` — crops image regions using bounding box coordinates from JSON
