"""Measure this machine's per-page pipeline cost and project a full benchmark run.

Dolphin inference dominates the runtime and is hardware-bound, so the only
honest way to plan a full run is to time real pages here first.

Concurrency is measured against a single-worker baseline, never assumed. Each
worker holds its own copy of the model, so on a machine short of cores or
memory more workers can make throughput worse, not better.
"""

import argparse
import itertools
import json
import platform
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from genieparse_bench.paths import pipeline_dir, pipeline_python
from genieparse_bench.runner import run_pipeline

# Unique human-verified pages in the published ParseBench dataset. Used only when
# no local dataset has been downloaded yet.
PARSEBENCH_PAGES = 2078


@dataclass
class Measurement:
    """What one calibration run observed."""

    timings: list[float]
    wall: float
    workers: int
    pages: int
    baseline: float | None
    pages_explicit: bool

    @property
    def runs(self) -> int:
        """How many pages were timed."""
        return len(self.timings)

    @property
    def per_page(self) -> float:
        """Throughput: seconds of wall clock each page costs at this concurrency."""
        return self.wall / self.runs

    @property
    def latency(self) -> float:
        """Mean time one page took end to end."""
        return statistics.mean(self.timings)

    @property
    def projected(self) -> float:
        """Wall-clock seconds for the whole set at this concurrency."""
        return self.per_page * self.pages


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

    The small test subset under data/test is a smoke test, not something worth
    projecting a full run from, so it is excluded.
    """
    if not data_dir.exists():
        return None
    pdfs = {
        p.resolve()
        for p in data_dir.rglob("*.pdf")
        if "test" not in p.relative_to(data_dir).parts[:1]
    }
    return len(pdfs) or None


def pick_samples(explicit: str | None, data_dir: Path, count: int) -> list[Path]:
    """Choose `count` PDFs to time, preferring real dataset pages.

    Distinct pages matter: page density drives Dolphin's runtime far more than
    anything else, so timing one page repeatedly measures that page, not the set.
    """
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.exists():
            sys.exit(f"PDF not found: {path}")
        return [path] * count

    pool = sorted(data_dir.rglob("*.pdf"))
    if not pool:
        sample = pipeline_dir().parent / "sample_input_dir" / "sample.pdf"
        if not sample.exists():
            sys.exit(
                "No PDF to calibrate on. Run 'make bench-download-test' first, "
                "or pass --pdf /path/to/page.pdf"
            )
        pool = [sample]

    return list(itertools.islice(itertools.cycle(pool), count))


def human_duration(seconds: float) -> str:
    """Format a duration as hours and minutes."""
    hours, remainder = divmod(int(seconds), 3600)
    minutes = remainder // 60
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m {int(seconds) % 60}s"


def time_pages(samples: list[Path], workers: int) -> tuple[float, list[float]]:
    """Run the samples with `workers` in flight. Returns (wall clock, per-page times)."""

    def one(pdf: Path) -> float:
        started = time.perf_counter()
        run_pipeline(pdf)
        return time.perf_counter() - started

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        timings = list(pool.map(one, samples))
    return time.perf_counter() - started, timings


def measure(
    samples: list[Path], workers: int, pages: int, pages_explicit: bool
) -> Measurement:
    """Time the samples, with a single-worker baseline whenever concurrency is on."""
    baseline = None
    if workers > 1:
        # Without this, "speedup" would compare the batch against its own
        # degraded latency and always flatter the worker count.
        print("  baseline, 1 worker ... ", end="", flush=True)
        baseline, _ = time_pages(samples[:1], 1)
        print(f"{baseline:.1f}s")

    wall, timings = time_pages(samples, workers)
    return Measurement(timings, wall, workers, pages, baseline, pages_explicit)


def report(m: Measurement) -> None:
    """Print the measured timings, the projection, and what concurrency bought."""
    for index, seconds in enumerate(m.timings, start=1):
        print(f"  page {index}: {seconds:.1f}s")
    print()
    print(f"Wall clock  : {m.wall:.1f}s for {m.runs} page(s)")
    print(f"Per page    : {m.per_page:.1f}s of throughput at {m.workers} worker(s)")
    print(f"Latency     : {m.latency:.1f}s mean for one page")
    print(f"Projected   : {human_duration(m.projected)} for {m.pages} pages")
    if not m.pages_explicit and m.pages < PARSEBENCH_PAGES:
        print(
            f"              (only {m.pages} of {PARSEBENCH_PAGES} pages are downloaded, "
            "so this projection covers what is on disk)"
        )
    print()

    if m.baseline is None:
        print("Note: every page pays a fresh Dolphin model load. The pipeline spawns")
        print("      one inference subprocess per PDF, so that cost never amortises.")
        return

    speedup = m.baseline / m.per_page
    print(f"Baseline    : {m.baseline:.1f}s per page with 1 worker")
    if speedup >= 1.0:
        print(
            f"{m.workers} workers bought {speedup:.2f}x. At 1 worker it would take "
            f"{human_duration(m.baseline * m.pages)}."
        )
    else:
        print(
            f"WARNING: {m.workers} workers made it {1 / speedup:.2f}x SLOWER than 1 worker."
        )
        print("      Each worker holds its own copy of the model, so this machine is")
        print("      short of cores or memory. Try a lower BENCH_CONCURRENCY.")


def main() -> int:
    """Time real pages and report the projected cost of a full run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", help="Time this PDF instead of dataset pages")
    parser.add_argument(
        "--runs", type=int, help="Pages to time (default: one per worker)"
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
        help="Workers to measure with (default: 1)",
    )
    parser.add_argument("--data-dir", default="data", help="Dataset directory")
    parser.add_argument(
        "--output", default="calibration.json", help="Where to write the result"
    )
    args = parser.parse_args()

    workers = max(args.concurrency, 1)
    data_dir = Path(args.data_dir).expanduser().resolve()
    samples = pick_samples(args.pdf, data_dir, max(args.runs or workers, 1))
    pages = args.pages or count_dataset_pages(data_dir) or PARSEBENCH_PAGES
    device = torch_device()

    print(f"Machine     : {platform.platform()}")
    print(f"Processor   : {platform.processor() or platform.machine()}")
    print(f"Dolphin runs: {device}")
    print(f"Timing      : {len(samples)} page(s), {workers} in flight")
    print()

    try:
        m = measure(samples, workers, pages, bool(args.pages))
    except subprocess.CalledProcessError as e:
        sys.exit(f"Pipeline exited {e.returncode}:\n{(e.stderr or '')[-2000:]}")
    except subprocess.TimeoutExpired as e:
        sys.exit(f"Pipeline timed out after {e.timeout:.0f}s")

    report(m)

    output = Path(args.output).expanduser().resolve()
    output.write_text(
        json.dumps(
            {
                "platform": platform.platform(),
                "processor": platform.processor() or platform.machine(),
                "device": device,
                "samples": [str(s) for s in samples],
                "concurrency": m.workers,
                "runs": m.runs,
                "page_seconds": [round(t, 2) for t in m.timings],
                "wall_seconds": round(m.wall, 2),
                "seconds_per_page": round(m.per_page, 2),
                "mean_latency_seconds": round(m.latency, 2),
                "baseline_seconds_per_page": (
                    round(m.baseline, 2) if m.baseline else None
                ),
                "speedup_vs_one_worker": (
                    round(m.baseline / m.per_page, 2) if m.baseline else None
                ),
                "pages": m.pages,
                "projected_seconds": round(m.projected, 2),
                "projected_human": human_duration(m.projected),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Saved       : {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
