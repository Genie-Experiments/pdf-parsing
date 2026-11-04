"""Running the GenieParse pipeline over a single PDF and collecting its output."""

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from genieparse_bench.paths import pipeline_dir, pipeline_python

# Steps 2-10 write shared state under <output>/_pipeline/, so every run gets its
# own output root — otherwise concurrent pages overwrite each other's raw text
# and section hierarchies.
_PIPELINE_SCRATCH = "_pipeline"
_SCRATCH_PREFIX = "genieparse_bench_"

# A page that has not finished in this long is stuck, not slow: the slowest
# pages measured so far are under two minutes.
DEFAULT_PAGE_TIMEOUT_S = float(os.environ.get("GENIEPARSE_PAGE_TIMEOUT", "1200"))

# Scratch older than this belongs to a run that was killed before it could clean up.
_STALE_SCRATCH_AGE_S = 6 * 3600


def _cache_enabled() -> bool:
    """Whether to use prewarmed Dolphin output when it exists.

    On by default, because a cache only exists if someone ran `make
    bench-prewarm` deliberately. Set GENIEPARSE_USE_DOLPHIN_CACHE=0 to force
    inference per page -- for instance to confirm the cache is not changing
    results.
    """
    return os.environ.get("GENIEPARSE_USE_DOLPHIN_CACHE", "1").lower() not in (
        "0",
        "false",
        "no",
    )


def scratch_root() -> Path:
    """Where per-page scratch directories live. Override with GENIEPARSE_SCRATCH_DIR."""
    env = os.environ.get("GENIEPARSE_SCRATCH_DIR")
    if env:
        root = Path(env).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root
    return Path(tempfile.gettempdir())


def sweep_stale_scratch() -> int:
    """Delete scratch left behind by runs that were killed. Returns how many."""
    removed = 0
    cutoff = time.time() - _STALE_SCRATCH_AGE_S
    for path in scratch_root().glob(f"{_SCRATCH_PREFIX}*"):
        try:
            if path.is_dir() and path.stat().st_mtime < cutoff:
                shutil.rmtree(path, ignore_errors=True)
                removed += 1
        except OSError:
            continue
    return removed


def run_pipeline(
    pdf_path: Path,
    config: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Parse one PDF and return its markdown and Dolphin JSON.

    Raises CalledProcessError if the pipeline exits non-zero, TimeoutExpired if
    it outlives `timeout`, and FileNotFoundError if it exits cleanly without
    producing markdown.
    """
    config = config or {}
    pipeline_root = pipeline_dir()
    main_py = pipeline_root / "main.py"
    if not main_py.exists():
        raise FileNotFoundError(
            f"Pipeline entry point not found at {main_py}. "
            "Set GENIEPARSE_PIPELINE_DIR to the directory holding main.py."
        )

    cmd = [str(pipeline_python()), str(main_py), "--pdf-file", str(pdf_path)]
    for flag, key in (
        ("--refine-tables", "refine_tables"),
        ("--refine-code", "refine_code"),
        ("--refine-figures", "refine_figures"),
        ("--process-code-llm", "process_code_llm"),
        ("--process-figures-llm", "process_figures_llm"),
    ):
        if config.get(key):
            cmd.append(flag)

    with tempfile.TemporaryDirectory(
        prefix=_SCRATCH_PREFIX, dir=str(scratch_root())
    ) as out_root:
        env = dict(os.environ)
        env["OUTPUT_DIRECTORY"] = out_root
        env["RESUME"] = "false"

        # Imported here rather than at module scope: genieparse_bench/__init__
        # imports this module, so a top-level import would leave prewarm in
        # sys.modules before `python -m genieparse_bench.prewarm` executes it,
        # and runpy warns about exactly that.
        from genieparse_bench import prewarm  # pylint: disable=import-outside-toplevel

        # If this page was prewarmed, Dolphin already ran for it with the model
        # loaded once for a whole chunk instead of once for this page. Stage
        # that output where steps 2-10 expect it and skip step 1.
        cached = prewarm.lookup(pdf_path.stem) if _cache_enabled() else None
        if cached is not None:
            prewarm.stage(cached, Path(out_root))
            env["START_FROM_STEP"] = "2"
        else:
            env["START_FROM_STEP"] = "1"

        completed = subprocess.run(
            cmd,
            cwd=str(pipeline_root),
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout if timeout is not None else DEFAULT_PAGE_TIMEOUT_S,
        )

        return _collect(Path(out_root), completed.stderr)


def _collect(out_root: Path, stderr: str) -> dict[str, Any]:
    """Read markdown and Dolphin JSON out of a finished pipeline run."""
    doc_dirs = [
        d for d in out_root.iterdir() if d.is_dir() and d.name != _PIPELINE_SCRATCH
    ]
    if not doc_dirs:
        raise FileNotFoundError(
            f"Pipeline produced no output directory under {out_root}. stderr: {stderr[-2000:]}"
        )

    doc_dir = doc_dirs[0]
    md_files = sorted(doc_dir.glob("markdown/*.md"))
    # Step 4 writes <stem>_backup.md next to the real output; ignore it.
    md_files = [p for p in md_files if not p.name.endswith("_backup.md")]
    if not md_files:
        raise FileNotFoundError(
            f"Pipeline produced no markdown under {doc_dir}. stderr: {stderr[-2000:]}"
        )

    markdown = md_files[0].read_text(encoding="utf-8")

    recognition: dict[str, Any] | None = None
    json_files = sorted(doc_dir.glob("recognition_json/*.json"))
    if json_files:
        try:
            recognition = json.loads(json_files[0].read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            recognition = None

    return {"markdown": markdown, "recognition_json": recognition}
