"""Measure this machine's per-page pipeline cost and project a full benchmark run.

Dolphin inference dominates the runtime and is hardware-bound, so the only
honest way to plan a full run is to time a page here first.
"""

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

from genieparse_bench.paths import pipeline_dir, pipeline_python
from genieparse_bench.runner import run_pipeline

# Unique human-verified pages in the published ParseBench dataset. Used only when
# no local dataset has been downloaded yet.
PARSEBENCH_PAGES = 2078


def torch_device() -> str:
    """Report the device Dolphin will actually use, by asking the pipeline's torch."""
    probe = (
        "import torch;"
        "print('cuda' if torch.cuda.is_available() else 'cpu');"
        "print(torch.__version__);"
        "print(torch.backends.mps.is_available())"
    )
    try:
        out = subprocess.run(
            [str(pipeline_python()), "-c", probe],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        return f"unknown ({e})"

    device, version, mps = out[0], out[1], out[2] == "True"
    note = ""
    if device == "cpu" and mps:
        # Dolphin's demo_page.py selects cuda-or-cpu only, so MPS goes unused.
        note = " (MPS available but unused by Dolphin)"
    return f"{device}, torch {version}{note}"


def count_dataset_pages(data_dir: Path) -> int | None:
    """Count PDFs in the full downloaded dataset, if one is present.

    The 12-page test subset lives under data/test and is a smoke test, not
    something worth projecting a full run from, so it is excluded.
    """
    if not data_dir.exists():
        return None
    pdfs = {
        p.resolve()
        for p in data_dir.rglob("*.pdf")
        if "test" not in p.relative_to(data_dir).parts[:1]
    }
    return len(pdfs) or None


def pick_sample(explicit: str | None, data_dir: Path) -> Path:
    """Prefer an explicit PDF, then a real benchmark page, then the repo sample."""
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.exists():
            sys.exit(f"PDF not found: {path}")
        return path

    for candidate in sorted(data_dir.rglob("*.pdf")):
        return candidate

    sample = pipeline_dir().parent / "sample_input_dir" / "sample.pdf"
    if sample.exists():
        return sample

    sys.exit(
        "No PDF to calibrate on. Run 'make bench-download-test' first, "
        "or pass --pdf /path/to/page.pdf"
    )


def human_duration(seconds: float) -> str:
    """Format a duration as hours and minutes."""
    hours, remainder = divmod(int(seconds), 3600)
    minutes = remainder // 60
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m {int(seconds) % 60}s"


def main() -> int:
    """Time a page and report the projected cost of a full run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pdf", help="PDF to time (default: a dataset page, else the repo sample)"
    )
    parser.add_argument(
        "--runs", type=int, default=1, help="Timed runs to average (default: 1)"
    )
    parser.add_argument(
        "--pages",
        type=int,
        help=f"Pages to project for (default: dataset size, else {PARSEBENCH_PAGES})",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Assumed parallel workers for the projection (default: 1)",
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="ParseBench dataset directory (default: ./data)",
    )
    parser.add_argument(
        "--output",
        default="calibration.json",
        help="Where to write the result (default: ./calibration.json)",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir).expanduser().resolve()
    sample = pick_sample(args.pdf, data_dir)
    pages = args.pages or count_dataset_pages(data_dir) or PARSEBENCH_PAGES
    device = torch_device()

    print(f"Machine     : {platform.platform()}")
    print(f"Processor   : {platform.processor() or platform.machine()}")
    print(f"Dolphin runs: {device}")
    print(f"Sample PDF  : {sample}")
    print(f"Timed runs  : {args.runs}")
    print()

    timings: list[float] = []
    for attempt in range(1, args.runs + 1):
        print(f"  run {attempt}/{args.runs} … ", end="", flush=True)
        started = time.perf_counter()
        try:
            run_pipeline(sample)
        except subprocess.CalledProcessError as e:
            print("failed")
            sys.exit(f"Pipeline exited {e.returncode}:\n{(e.stderr or '')[-2000:]}")
        elapsed = time.perf_counter() - started
        timings.append(elapsed)
        print(f"{elapsed:.1f}s")

    per_page = statistics.mean(timings)
    projected = per_page * pages / max(args.concurrency, 1)

    print()
    print(
        f"Per page    : {per_page:.1f}s"
        + (f" (median {statistics.median(timings):.1f}s)" if len(timings) > 1 else "")
    )
    print(f"Pages       : {pages}")
    print(f"Concurrency : {args.concurrency}")
    print(f"Projected   : {human_duration(projected)} for a full run")
    print()
    print("Note: each page pays a fresh Dolphin model load — the pipeline spawns one")
    print(
        "      inference subprocess per PDF, so this cost does not amortise in batch."
    )

    result = {
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "device": device,
        "sample_pdf": str(sample),
        "runs": timings,
        "seconds_per_page": round(per_page, 2),
        "pages": pages,
        "concurrency": args.concurrency,
        "projected_seconds": round(projected, 2),
        "projected_human": human_duration(projected),
    }
    output = Path(args.output).expanduser().resolve()
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Saved       : {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
