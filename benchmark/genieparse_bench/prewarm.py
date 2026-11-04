"""Pre-computing Dolphin inference in chunks, so a run loads the model once per
chunk instead of once per page.

The pipeline spawns one Dolphin subprocess per PDF, so every page pays a fresh
cold start. Measured on an Apple M3: 4.96s, of which importing torch and
transformers is 4.26s and loading the 398M-parameter weights is only 0.18s.
On CPU that hides behind ~26s of inference and looks like noise. On a GPU it
does not: inference shrinks, the import cost does not, and the card sits idle
for a large share of every page.

Dolphin's own CLI accepts a directory and processes it with a single model
load, so this module feeds it the dataset in chunks. One load per chunk
instead of one per page. Dolphin writes each page's output as it finishes, so
an interrupted pass loses only the page in flight: everything already written
stays cached, and re-running re-chunks whatever is left.

The cache is keyed on the PDF stem, which is what both the pipeline and
parse-bench use as the document name.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from genieparse_bench.paths import pipeline_dir, pipeline_python

DEFAULT_CHUNK_SIZE = 50
DEFAULT_MAX_BATCH_SIZE = 16

# Dolphin gets the same per-page budget the per-page path uses, times the
# chunk size, so a slow chunk is not killed for being a chunk.
_TIMEOUT_PER_PAGE_S = 1200


def cache_root() -> Path:
    """Where pre-computed Dolphin output lives.

    Override with GENIEPARSE_DOLPHIN_CACHE -- useful to put it on the same
    fast disk as the dataset, or to share one cache between runs.
    """
    env = os.environ.get("GENIEPARSE_DOLPHIN_CACHE")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parent.parent / "dolphin-cache"


def dataset_root() -> Path:
    """Where `genieparse-bench download` puts the ParseBench PDFs."""
    return Path(__file__).resolve().parent.parent / "data" / "docs"


@dataclass(frozen=True)
class CachedPage:
    """Dolphin output for one document, as it sits in the cache."""

    stem: str
    markdown: Path
    recognition: Path | None
    figures: tuple[Path, ...]
    page_images: tuple[Path, ...]


def lookup(stem: str, root: Path | None = None) -> CachedPage | None:
    """Cached Dolphin output for a document stem, or None if it is not there.

    Markdown is the marker: Dolphin writes it last, so its presence means the
    page completed. A half-written chunk leaves no markdown for the page it
    died on, which is what makes an interrupted prewarm safe to resume.
    """
    root = root or cache_root()
    markdown = root / "markdown" / f"{stem}.md"
    if not markdown.exists():
        return None

    recognition = root / "recognition_json" / f"{stem}.json"
    figures = tuple(sorted((root / "markdown" / "figures").glob(f"{stem}_page_*")))
    page_images = tuple(sorted((root / "_imgs" / stem).glob("*.png")))
    return CachedPage(
        stem=stem,
        markdown=markdown,
        recognition=recognition if recognition.exists() else None,
        figures=figures,
        page_images=page_images,
    )


def stage(cached: CachedPage, out_root: Path) -> None:
    """Lay cached output out the way process_pdf_files would have.

    Steps 2-10 read Dolphin's output from OUTPUT_DIRECTORY/<stem>/, so writing
    it there lets the pipeline run with START_FROM_STEP=2 and skip inference
    entirely. Everything is copied rather than linked, because steps 5-10
    rewrite the markdown in place and must never reach back into the cache.
    """
    doc = out_root / cached.stem
    markdown_dir = doc / "markdown"
    markdown_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cached.markdown, markdown_dir / f"{cached.stem}.md")

    if cached.recognition is not None:
        recognition_dir = doc / "recognition_json"
        recognition_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cached.recognition, recognition_dir / f"{cached.stem}.json")

    if cached.figures:
        figures_dir = markdown_dir / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)
        for figure in cached.figures:
            shutil.copy2(figure, figures_dir / figure.name)

    if cached.page_images:
        images_dir = doc / "Dolphin" / "imgs_pages"
        images_dir.mkdir(parents=True, exist_ok=True)
        for image in cached.page_images:
            shutil.copy2(image, images_dir / image.name)


def find_pdfs(root: Path | None = None) -> list[Path]:
    """Every PDF in the dataset, in a stable order."""
    root = root or dataset_root()
    return sorted(root.rglob("*.pdf"))


def pending(pdfs: list[Path], root: Path | None = None) -> list[Path]:
    """The PDFs that have no cached Dolphin output yet."""
    root = root or cache_root()
    return [pdf for pdf in pdfs if lookup(pdf.stem, root) is None]


def _run_chunk(
    chunk: list[Path],
    root: Path,
    max_batch_size: int,
) -> None:
    """One Dolphin invocation over a staged directory: one model load."""
    pipeline_root = pipeline_dir()
    dolphin = pipeline_root / "Dolphin" / "demo_page.py"
    if not dolphin.exists():
        raise FileNotFoundError(
            f"Dolphin entry point not found at {dolphin}. "
            "Run 'make submodules' to check out the Dolphin submodule."
        )

    with tempfile.TemporaryDirectory(prefix="genieparse-prewarm-") as staging:
        staged = Path(staging)
        for pdf in chunk:
            # Two dimensions can hold a PDF with the same filename. Within one
            # chunk that would silently drop a page, so keep the first and let
            # the duplicate fall through to its own chunk or the per-page path.
            target = staged / pdf.name
            if not target.exists():
                shutil.copy2(pdf, target)

        cmd = [
            str(pipeline_python()),
            str(dolphin),
            "--model_path",
            str(pipeline_root / "hf_model"),
            "--input_path",
            str(staged),
            "--save_dir",
            str(root),
            "--processed_images_dir",
            str(root / "_imgs"),
            "--max_batch_size",
            str(max_batch_size),
        ]
        subprocess.run(
            cmd,
            cwd=str(pipeline_root),
            check=True,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_PER_PAGE_S * len(chunk),
        )


def prewarm(
    pdfs: list[Path] | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    root: Path | None = None,
    max_batch_size: int = DEFAULT_MAX_BATCH_SIZE,
    log=print,
) -> dict[str, int]:
    """Fill the cache, one model load per chunk.

    Returns counts of what was already there and what this call produced.
    """
    root = root or cache_root()
    root.mkdir(parents=True, exist_ok=True)

    pdfs = pdfs if pdfs is not None else find_pdfs()
    if not pdfs:
        raise FileNotFoundError(
            f"No PDFs under {dataset_root()}. Run 'make bench-download' first."
        )

    todo = pending(pdfs, root)
    cached_already = len(pdfs) - len(todo)
    log(f"{len(pdfs)} pages in the dataset, {cached_already} already cached.")
    if not todo:
        log("Nothing to do.")
        return {"total": len(pdfs), "cached": cached_already, "written": 0}

    chunks = [todo[i : i + chunk_size] for i in range(0, len(todo), chunk_size)]
    log(
        f"Running {len(todo)} pages as {len(chunks)} chunk(s) of up to "
        f"{chunk_size} — {len(chunks)} model load(s) instead of {len(todo)}."
    )

    for index, chunk in enumerate(chunks, start=1):
        log(f"  chunk {index}/{len(chunks)}: {len(chunk)} pages")
        _run_chunk(chunk, root, max_batch_size)

    written = len(pdfs) - len(pending(pdfs, root)) - cached_already
    log(f"Cached {written} new page(s) at {root}.")
    return {"total": len(pdfs), "cached": cached_already, "written": written}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: fill the Dolphin cache for the downloaded dataset."""
    parser = argparse.ArgumentParser(
        description=(
            "Pre-compute Dolphin inference for the dataset, loading the model "
            "once per chunk instead of once per page."
        )
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=(
            "Pages per Dolphin invocation (default: %(default)s). Larger means "
            "fewer model loads; an interruption costs the chunk in flight."
        ),
    )
    parser.add_argument(
        "--max-batch-size",
        type=int,
        default=DEFAULT_MAX_BATCH_SIZE,
        help="Dolphin's own element batch size (default: %(default)s).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only prewarm the first N uncached pages. Useful for a trial run.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help=(
            "Directory of PDFs to prewarm (default: the downloaded dataset at "
            "%(default)s). Point it at data/test for the smoke set, or at one "
            "dimension to prewarm it alone."
        ),
    )
    args = parser.parse_args(argv)

    pdfs = find_pdfs(args.data_dir)
    if not pdfs:
        where = args.data_dir or dataset_root()
        print(
            f"No PDFs under {where}. Run 'make bench-download' first.",
            file=sys.stderr,
        )
        return 1
    if args.limit is not None:
        root = cache_root()
        done = [p for p in pdfs if lookup(p.stem, root) is not None]
        pdfs = done + pending(pdfs, root)[: args.limit]

    try:
        prewarm(
            pdfs,
            chunk_size=args.chunk_size,
            max_batch_size=args.max_batch_size,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()[-2000:]
        print(f"Dolphin failed (exit {exc.returncode}): {stderr}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
