"""Pre-computing Dolphin inference in chunks, so a run loads the model once per
chunk instead of once per page.

The pipeline spawns one Dolphin subprocess per PDF, so every page pays a fresh
cold start. Measured on an Apple M3: 4.96s, of which importing torch and
transformers is 4.26s and loading the 398M-parameter weights is only 0.18s.
On CPU that hides behind ~16s of inference and looks like noise. On a GPU it
does not: inference shrinks, the import cost does not, and the card sits idle
for a large share of every page.

Dolphin's own CLI accepts a directory and processes it with a single model
load, so this module feeds it the dataset in chunks. One load per chunk
instead of one per page. Dolphin writes each page's output as it finishes, so
an interrupted pass loses only the page in flight: everything already written
stays cached, and re-running re-chunks whatever is left.

Entries are keyed on the PDF's content, not its name. parse-bench does not hand
the provider the dataset file -- it materialises each example to a temporary
file with a generated name (`101cf170df9ba6d4-form.pdf`) -- so a name-keyed
cache never matches. Content keying also means two dataset entries holding the
same page are inferred once.

Dolphin names figures after the input file, and the markdown links to them by
that name -- and that markdown is what ParseBench scores. So cached output is
renamed back to the caller's stem on the way out; see `stage`.
"""

from __future__ import annotations

import argparse
import hashlib
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

# 16 hex characters of SHA-256. Collisions are not a practical concern across a
# few thousand pages, and short keys keep a cache listing readable.
_KEY_LENGTH = 16
_HASH_BLOCK_BYTES = 1 << 20

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


def content_key(pdf_path: Path) -> str:
    """Cache key for a PDF: a prefix of the SHA-256 of its bytes.

    Keyed on content rather than filename, because the name the provider is
    handed is not the name the dataset uses.
    """
    digest = hashlib.sha256()
    with open(pdf_path, "rb") as handle:
        for block in iter(lambda: handle.read(_HASH_BLOCK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()[:_KEY_LENGTH]


@dataclass(frozen=True)
class CachedPage:
    """Dolphin output for one document, as it sits in the cache."""

    key: str
    markdown: Path
    recognition: Path | None
    figures: tuple[Path, ...]
    page_images: tuple[Path, ...]


def lookup(pdf_path: Path, root: Path | None = None) -> CachedPage | None:
    """Cached Dolphin output for a PDF, or None if it is not there.

    Markdown is the marker: Dolphin writes it when a page completes, so its
    presence means that page is done and an interrupted pass is safe to resume.
    """
    root = root or cache_root()
    try:
        key = content_key(pdf_path)
    except OSError:
        return None
    return lookup_key(key, root)


def lookup_key(key: str, root: Path | None = None) -> CachedPage | None:
    """Cached output for an already-computed key."""
    root = root or cache_root()
    markdown = root / "markdown" / f"{key}.md"
    if not markdown.exists():
        return None

    recognition = root / "recognition_json" / f"{key}.json"
    figures = tuple(sorted((root / "markdown" / "figures").glob(f"{key}_page_*")))
    page_images = tuple(sorted((root / "_imgs" / key).glob("*.png")))
    return CachedPage(
        key=key,
        markdown=markdown,
        recognition=recognition if recognition.exists() else None,
        figures=figures,
        page_images=page_images,
    )


def stage(cached: CachedPage, out_root: Path, stem: str) -> None:
    """Lay cached output out the way process_pdf_files would have for `stem`.

    Steps 2-10 read Dolphin's output from OUTPUT_DIRECTORY/<stem>/, so writing
    it there lets the pipeline run with START_FROM_STEP=2 and skip inference.

    The cache stores output under its content key, but figures are named after
    the input file and the markdown links to them by that name. Renaming the
    figures to the caller's stem and rewriting the links reproduces exactly
    what inference on `<stem>.pdf` would have written -- which matters, because
    that markdown is the text ParseBench scores.

    Everything is copied rather than linked: steps 5-10 rewrite the markdown in
    place and must never reach back into the cache.
    """
    doc = out_root / stem
    markdown_dir = doc / "markdown"
    markdown_dir.mkdir(parents=True, exist_ok=True)

    text = cached.markdown.read_text(encoding="utf-8")
    if cached.key != stem:
        text = text.replace(f"figures/{cached.key}_", f"figures/{stem}_")
    (markdown_dir / f"{stem}.md").write_text(text, encoding="utf-8")

    if cached.recognition is not None:
        recognition_dir = doc / "recognition_json"
        recognition_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cached.recognition, recognition_dir / f"{stem}.json")

    if cached.figures:
        figures_dir = markdown_dir / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)
        for figure in cached.figures:
            name = figure.name.replace(f"{cached.key}_", f"{stem}_", 1)
            shutil.copy2(figure, figures_dir / name)

    if cached.page_images:
        images_dir = doc / "Dolphin" / "imgs_pages"
        images_dir.mkdir(parents=True, exist_ok=True)
        for image in cached.page_images:
            shutil.copy2(image, images_dir / image.name)


def find_pdfs(root: Path | None = None) -> list[Path]:
    """Every PDF under a directory, in a stable order."""
    root = root or dataset_root()
    return sorted(root.rglob("*.pdf"))


def pending(pdfs: list[Path], root: Path | None = None) -> list[Path]:
    """The PDFs with no cached output yet, one per distinct content key.

    Two dataset entries holding the same page collapse to a single inference.
    """
    root = root or cache_root()
    seen: set[str] = set()
    todo: list[Path] = []
    for pdf in pdfs:
        key = content_key(pdf)
        if key in seen or lookup_key(key, root) is not None:
            continue
        seen.add(key)
        todo.append(pdf)
    return todo


def _run_chunk(chunk: list[Path], root: Path, max_batch_size: int) -> None:
    """One Dolphin invocation over a staged directory: one model load.

    PDFs are staged under their content key, so Dolphin names every artefact
    -- markdown, recognition JSON, figures -- after that key.
    """
    pipeline_root = pipeline_dir()
    dolphin = pipeline_root / "Dolphin" / "demo_page.py"
    if not dolphin.exists():
        raise FileNotFoundError(
            f"Dolphin entry point not found at {dolphin}. "
            "Run 'make submodules' to check out the Dolphin submodule."
        )

    sources = root / "sources"
    sources.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="genieparse-prewarm-") as staging:
        staged = Path(staging)
        for pdf in chunk:
            key = content_key(pdf)
            shutil.copy2(pdf, staged / f"{key}.pdf")
            # Not used for lookup -- just so someone reading the cache can tell
            # which page an opaque key belongs to.
            (sources / f"{key}.txt").write_text(f"{pdf}\n", encoding="utf-8")

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

    Returns how many pages were considered and how many this call produced.
    """
    root = root or cache_root()
    root.mkdir(parents=True, exist_ok=True)

    pdfs = pdfs if pdfs is not None else find_pdfs()
    if not pdfs:
        raise FileNotFoundError(
            f"No PDFs under {dataset_root()}. Run 'make bench-download' first."
        )

    todo = pending(pdfs, root)
    log(f"{len(pdfs)} pages in the dataset, {len(pdfs) - len(todo)} already cached.")
    if not todo:
        log("Nothing to do.")
        return {"total": len(pdfs), "written": 0}

    chunks = [todo[i : i + chunk_size] for i in range(0, len(todo), chunk_size)]
    log(
        f"Running {len(todo)} pages as {len(chunks)} chunk(s) of up to "
        f"{chunk_size} — {len(chunks)} model load(s) instead of {len(todo)}."
    )

    for index, chunk in enumerate(chunks, start=1):
        log(f"  chunk {index}/{len(chunks)}: {len(chunk)} pages")
        _run_chunk(chunk, root, max_batch_size)

    written = len(todo) - len(pending(pdfs, root))
    log(f"Cached {written} new page(s) at {root}.")
    return {"total": len(pdfs), "written": written}


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
            "fewer model loads; an interruption costs the page in flight."
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
            "Directory of PDFs to prewarm (default: the downloaded dataset). "
            "Point it at data/test for the smoke set, or at one dimension."
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
        done = [p for p in pdfs if lookup(p, root) is not None]
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
