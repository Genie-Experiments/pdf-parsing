"""
Streamlit UI for the PDF Parsing Pipeline.

Usage:
    streamlit run app.py
"""

import base64
import logging
import os
import queue
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

import streamlit as st

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="PDF Parser", layout="wide", page_icon="📄")

# ── project root on sys.path ─────────────────────────────────────────────────
ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ── log capture handler ───────────────────────────────────────────────────────
class QueueHandler(logging.Handler):
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))


# ── pipeline runner (runs in a background thread) ─────────────────────────────
def run_pipeline(
    pdf_path: Path, data_dir: Path, output_dir: Path, log_queue: queue.Queue
):
    """Execute the full 10-step pipeline for a single PDF."""
    try:
        # Lazy imports so they don't affect Streamlit's module scan
        from config.config import settings
        from post_processing.fix_bullet_points.fix_bullet_points import (
            fix_bullet_points_batch,
        )
        from post_processing.fix_ocr_errors.fix_ocr_errors import fix_ocr_errors_batch
        from post_processing.fix_ocr_errors.get_text_from_pdf import (
            extract_all_pdf_texts,
        )
        from post_processing.markdown_sections_post_processing.fix_markdown_sections import (
            batch_fix_markdown_sections,
        )
        from post_processing.markdown_sections_post_processing.section_hierarchy_from_pdf import (
            batch_process_pdfs,
        )
        from post_processing.process_json_files import process_all_json_files
        from post_processing.remove_headers_and_footers.insert_page_breaks import (
            insert_page_breaks_batch,
        )
        from post_processing.remove_headers_and_footers.remove_headers_footers import (
            remove_headers_footers_batch,
        )
        from process_pdf_files.process_pdf_files import process_pdf_files
        from utils.create_backups_md import create_markdown_backup
        from utils.logger import setup_logging

        DOLPHIN_SCRIPT = str(ROOT / "Dolphin" / "demo_page.py")
        MODEL_PATH = str(ROOT / "Dolphin" / "hf_model")
        RAW_PDF_TEXT_DIR = str(output_dir / "_pipeline" / "raw_text")
        HIERARCHY_JSON_DIR = str(output_dir / "_pipeline" / "section_hierarchy")

        data_dir_str = str(data_dir)
        output_dir_str = str(output_dir)

        # Attach queue handler to root logger
        root_logger = logging.getLogger()
        handler = QueueHandler(log_queue)
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)

        def step(n, label, fn):
            log_queue.put(f"\n{'='*60}\nSTEP {n}: {label}\n{'='*60}")
            fn()

        step(
            1,
            "Processing PDF with Dolphin model",
            lambda: process_pdf_files(
                data_dir_str, output_dir_str, DOLPHIN_SCRIPT, MODEL_PATH
            ),
        )

        step(
            2,
            "Extracting raw text from PDF",
            lambda: extract_all_pdf_texts(data_dir_str, RAW_PDF_TEXT_DIR),
        )

        step(
            3,
            "Generating section hierarchy JSONs",
            lambda: batch_process_pdfs(
                data_directory=data_dir_str,
                output_base_dir=HIERARCHY_JSON_DIR,
                min_heading_size=12,
                max_levels=6,
                bold_only=False,
                exclude_headers_footers=True,
            ),
        )

        step(
            4,
            "Creating markdown backups",
            lambda: create_markdown_backup(output_dir_str),
        )

        step(
            5,
            "Refining segments (tables, code, figures)",
            lambda: process_all_json_files(
                output_dir_str,
                settings.segments_to_refine,
                settings.process_code_using_llm,
                settings.process_figures_using_llm,
            ),
        )

        step(
            6, "Inserting page breaks", lambda: insert_page_breaks_batch(output_dir_str)
        )

        step(
            7,
            "Removing headers and footers",
            lambda: remove_headers_footers_batch(output_dir_str),
        )

        step(
            8,
            "Fixing OCR errors",
            lambda: fix_ocr_errors_batch(output_dir_str, RAW_PDF_TEXT_DIR),
        )

        step(
            9,
            "Fixing markdown section hierarchy",
            lambda: batch_fix_markdown_sections(HIERARCHY_JSON_DIR, output_dir_str),
        )

        step(
            10,
            "Standardizing bullet points",
            lambda: fix_bullet_points_batch(output_dir_str),
        )

        log_queue.put("__DONE__")

    except Exception as e:
        log_queue.put(f"[ERROR] Pipeline failed: {e}")
        log_queue.put("__ERROR__")
    finally:
        # Remove our handler so it doesn't leak into future runs
        for h in logging.getLogger().handlers[:]:
            if isinstance(h, QueueHandler):
                logging.getLogger().removeHandler(h)


# ── helpers ───────────────────────────────────────────────────────────────────
def pdf_iframe(pdf_bytes: bytes) -> str:
    b64 = base64.b64encode(pdf_bytes).decode()
    return f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="820px" style="border:none;"></iframe>'


def find_markdown(output_dir: Path) -> Path | None:
    mds = [
        p
        for p in output_dir.rglob("*.md")
        if "_backup" not in p.name and "_pipeline" not in str(p)
    ]
    return mds[0] if mds else None


# ── session state defaults ────────────────────────────────────────────────────
for key, val in {
    "running": False,
    "done": False,
    "error": False,
    "logs": [],
    "markdown_text": "",
    "temp_dir": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📄 PDF Parser")
    uploaded = st.file_uploader("Upload PDF", type="pdf")

    run_btn = st.button(
        "▶ Run Pipeline",
        disabled=(uploaded is None or st.session_state.running),
        use_container_width=True,
        type="primary",
    )

    if st.button("🔄 Reset", use_container_width=True):
        if st.session_state.temp_dir and Path(st.session_state.temp_dir).exists():
            shutil.rmtree(st.session_state.temp_dir, ignore_errors=True)
        for key, val in {
            "running": False,
            "done": False,
            "error": False,
            "logs": [],
            "markdown_text": "",
            "temp_dir": None,
        }.items():
            st.session_state[key] = val
        st.rerun()

    st.divider()
    st.caption("Pipeline runs all 10 post-processing steps.")


# ── trigger pipeline ──────────────────────────────────────────────────────────
if run_btn and uploaded and not st.session_state.running:
    # Create fresh temp dirs
    if st.session_state.temp_dir and Path(st.session_state.temp_dir).exists():
        shutil.rmtree(st.session_state.temp_dir, ignore_errors=True)

    tmp = tempfile.mkdtemp(prefix="pdf_parser_")
    st.session_state.temp_dir = tmp
    data_dir = Path(tmp) / "data"
    output_dir = Path(tmp) / "output"
    data_dir.mkdir()
    output_dir.mkdir()

    # Save PDF
    pdf_path = data_dir / uploaded.name
    pdf_path.write_bytes(uploaded.getvalue())

    # Reset state
    st.session_state.logs = []
    st.session_state.markdown_text = ""
    st.session_state.running = True
    st.session_state.done = False
    st.session_state.error = False

    log_q: queue.Queue = queue.Queue()
    st.session_state._log_queue = log_q

    thread = threading.Thread(
        target=run_pipeline,
        args=(pdf_path, data_dir, output_dir, log_q),
        daemon=True,
    )
    thread.start()
    st.session_state._thread = thread


# ── poll logs while running ───────────────────────────────────────────────────
if st.session_state.running:
    log_q = st.session_state.get("_log_queue")
    if log_q:
        while not log_q.empty():
            msg = log_q.get_nowait()
            if msg == "__DONE__":
                st.session_state.running = False
                st.session_state.done = True
                # Find markdown
                tmp = Path(st.session_state.temp_dir)
                md = find_markdown(tmp / "output")
                if md:
                    st.session_state.markdown_text = md.read_text(encoding="utf-8")
            elif msg == "__ERROR__":
                st.session_state.running = False
                st.session_state.error = True
            else:
                st.session_state.logs.append(msg)
    time.sleep(0.5)
    st.rerun()


# ── main layout ───────────────────────────────────────────────────────────────
if uploaded is None and not st.session_state.done:
    st.info("Upload a PDF in the sidebar to get started.")
    st.stop()

left, right = st.columns(2, gap="medium")

# ── LEFT: PDF viewer ──────────────────────────────────────────────────────────
with left:
    st.subheader("PDF")
    if uploaded:
        st.components.v1.html(
            pdf_iframe(uploaded.getvalue()), height=840, scrolling=False
        )
    else:
        st.empty()

# ── RIGHT: progress + markdown ────────────────────────────────────────────────
with right:
    if st.session_state.running or st.session_state.logs:
        label = (
            "⏳ Running pipeline…"
            if st.session_state.running
            else "✅ Pipeline complete"
        )
        with st.expander(label, expanded=st.session_state.running):
            log_text = "\n".join(st.session_state.logs[-200:])  # last 200 lines
            st.code(log_text, language=None)

    if st.session_state.error:
        st.error("Pipeline failed. Check logs above.")

    if st.session_state.done and st.session_state.markdown_text:
        st.subheader("Markdown Output")
        view = st.radio(
            "View", ["Preview", "Raw"], horizontal=True, label_visibility="collapsed"
        )
        st.divider()
        if view == "Preview":
            st.markdown(st.session_state.markdown_text)
        else:
            st.code(st.session_state.markdown_text, language="markdown")

    elif not st.session_state.running and not st.session_state.done and uploaded:
        st.info("Press **▶ Run Pipeline** in the sidebar.")
