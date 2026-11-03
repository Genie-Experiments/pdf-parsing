"""Locating the GenieParse pipeline and the interpreter that can run it."""

import os
import shutil
from pathlib import Path

# benchmark/genieparse_bench/paths.py -> repo root is two levels up
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def pipeline_dir() -> Path:
    """Directory holding the pipeline's main.py. Override with GENIEPARSE_PIPELINE_DIR."""
    env = os.environ.get("GENIEPARSE_PIPELINE_DIR")
    return Path(env).expanduser().resolve() if env else _REPO_ROOT / "pipeline"


def pipeline_python() -> Path:
    """Interpreter with the pipeline's ML deps. Override with GENIEPARSE_PYTHON.

    The pipeline keeps torch/transformers in its own venv, deliberately separate
    from parse-bench's dependency tree, so we invoke it rather than import it.
    """
    env = os.environ.get("GENIEPARSE_PYTHON")
    if env:
        return Path(env).expanduser().resolve()

    venv_python = pipeline_dir() / ".venv" / "bin" / "python"
    if venv_python.exists():
        return venv_python

    found = shutil.which("python3") or shutil.which("python")
    if not found:
        raise FileNotFoundError("No Python interpreter found for the pipeline.")
    return Path(found)
