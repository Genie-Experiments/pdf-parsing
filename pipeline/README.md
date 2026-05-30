# pdf-pipeline

Extracts clean Markdown from PDFs using ByteDance's [Dolphin](https://github.com/bytedance/Dolphin) model, followed by a 10-step post-processing pipeline. Can run standalone from the CLI, or be imported as a package by the backend worker.

**[→ Flow diagram](flow_diagram.md)** — end-to-end Mermaid diagram showing all steps, data dependencies, segment dispatch, and config gates.

## Structure

```
pipeline/
├── main.py                     CLI entry point — runs all 10 steps
├── config/config.py            Pydantic Settings — all configuration
├── process_pdf_files/          Step 1 — Dolphin subprocess wrapper
├── post_processing/            Steps 2–10 — all post-processing logic
├── utils/                      Logger, path helpers, image cropping
├── evaluation_scripts/         Standalone accuracy comparison tools
├── Dolphin/                    git submodule — ByteDance layout model
└── html-to-markdown/           git submodule — Go HTML→Markdown converter
```

## Setup (one-time)

```bash
# From repo root — installs ML deps + downloads Dolphin weights (~5 GB)
make setup-pipeline

# NVIDIA GPU (Linux/Windows only)
make setup-pipeline-gpu                    # default CUDA cu124
make setup-pipeline-gpu CUDA_VERSION=cu121 # override CUDA version
```

> If you only need steps 2–10 (skipping Dolphin inference), `cd pipeline && uv sync` is sufficient and much faster — no ML stack needed.

## Configure

```bash
cd pipeline
cp .env.example .env
# Edit .env — set DATA_DIRECTORY (required unless using --pdf-file)
```

Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIRECTORY` | — | Input PDF directory. Required unless using `--pdf-file`. |
| `OUTPUT_DIRECTORY` | `./Results` | Where pipeline writes output |
| `RESUME` | `false` | Skip steps whose outputs already exist |
| `START_FROM_STEP` | `1` | Start from step N (1–10). Use `2` to skip Dolphin re-inference. |
| `OPENAI_API_KEY` | — | Required only if `--process-code-llm` or `--process-figures-llm` is passed |
| `DOLPHIN_MAX_BATCH_SIZE` | `16` | Increase for more RAM/VRAM |

## Run

All commands from inside `pipeline/`:

```bash
# Full directory of PDFs
uv run python main.py --data-dir /path/to/pdfs

# Or set DATA_DIRECTORY in .env and just run
uv run python main.py

# Single PDF file
uv run python main.py --pdf-file /path/to/doc.pdf

# Single page of a PDF (1-indexed) — extracted page saved next to original
uv run python main.py --pdf-file /path/to/doc.pdf --page 5

# Skip Dolphin re-inference, re-run post-processing only
START_FROM_STEP=2 uv run python main.py --data-dir /path/to/pdfs

# Resume a partial run — skip steps whose outputs already exist
RESUME=true uv run python main.py --data-dir /path/to/pdfs

# Refine tables only
uv run python main.py --pdf-file /path/to/doc.pdf --refine-tables

# Refine all three segment types
uv run python main.py --pdf-file /path/to/doc.pdf --refine-tables --refine-code --refine-figures

# Refine code with LLM, and figures with LLM
uv run python main.py --pdf-file /path/to/doc.pdf --refine-code --refine-figures --process-code-llm --process-figures-llm
```

## Output

```
Results/
└── <doc_name>/
    ├── recognition_json/<doc_name>.json   Dolphin layout JSON (bounding boxes)
    └── markdown/
        ├── <doc_name>.md                  Final post-processed Markdown
        ├── <doc_name>_backup.md           Pre-mutation backup (step 4)
        ├── <doc_name>_corrections.json    OCR correction log (step 8)
        └── figures/*.png                  Extracted figure images
```

For `--page N` runs, output is under `<doc_name>_page#N/`.

## Pipeline Steps

| Step | Description |
|------|-------------|
| 1 | **Dolphin inference** — extracts baseline Markdown + layout JSON |
| 2 | **Raw text extraction** — PyMuPDF text saved as OCR reference |
| 3 | **Section hierarchy** — font metric analysis → heading level JSON |
| 4 | **Backup** — copies `.md` files before any mutation |
| 5 | **Segment refinement** — tables → Markdown, code cleanup, optional LLM |
| 6 | **Insert page breaks** — replaces `---` with `<!-- page_break_N -->` |
| 7 | **Remove headers/footers** — strips repetitive cross-page content |
| 8 | **Fix OCR errors** — fuzzy-matches Markdown against raw text |
| 9 | **Fix section hierarchy** — corrects heading levels using JSON from step 3 |
| 10 | **Standardize bullets** — converts `•`, `◦`, etc. to `-` |

Steps 3 and 9 are tightly coupled: step 3 writes a hierarchy JSON, step 9 reads it.

## Evaluation

```bash
# Word/character accuracy vs ground truth
uv run python evaluation_scripts/compare_text.py \
  --generated path/to/generated.md \
  --ground-truth path/to/gt.md

# Section hierarchy accuracy (precision / recall / F1)
uv run python evaluation_scripts/sections_accuracy_comparison.py \
  --generated path/to/generated.md \
  --ground-truth path/to/gt.md
```

## Logging

Use the provided helpers — never `print` or `logging` directly:

```python
from utils.logger import log_step, log_success, log_error, log_warning

log_step("Processing PDF")
log_success("Done")
```

Logs go to console (colored) and `logs/pdf_parsing.log` (rotating, 10 MB, 5 backups).
