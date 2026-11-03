"""Report how far a benchmark run has got, and what is left.

Inference results are written one JSON file per page, so progress survives a
crash and can be read back without the run being alive.
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Inference writes one directory per source corpus, not per scored dimension:
# text_content and text_formatting are both graded from docs/text.
GROUPS = ("chart", "layout", "table", "text")


def valid_results(group_dir: Path) -> int:
    """Count results parse-bench will accept on resume.

    Mirrors its own check: a result counts only if it parses and carries both
    `request` and `output`, so a file truncated by a crash is not counted here
    either — it will simply be redone.
    """
    count = 0
    for path in group_dir.glob("*.result.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if "request" in data and "output" in data:
            count += 1
    return count


def count_inputs(data_dir: Path, group: str) -> int | None:
    """How many PDFs the dataset holds for one dimension.

    Falls back to the test subset so progress reads sensibly after a smoke test,
    before the full dataset has been downloaded.
    """
    for root in (data_dir, data_dir / "test"):
        group_dir = root / "docs" / group
        if group_dir.exists():
            return len({p.resolve() for p in group_dir.glob("*.pdf")})
    return None


def read_running_pid(pid_file: Path) -> int | None:
    """Return the pid of a live background run, if there is one."""
    try:
        pid = int(pid_file.read_text().strip())
    except (OSError, ValueError):
        return None
    try:
        os.kill(pid, 0)
    except OSError:
        return None
    return pid


def report_progress(output_dir: Path, data_dir: Path) -> tuple[int, int]:
    """Print the per-dimension table. Returns (done, expected) totals."""
    done_total = 0
    expected_total = 0
    print(f"{'Dimension':<18}{'Done':>8}{'Total':>8}  Progress")
    for group in GROUPS:
        group_dir = output_dir / group
        done = valid_results(group_dir) if group_dir.exists() else 0
        expected = count_inputs(data_dir, group)
        done_total += done
        if expected:
            expected_total += expected
            pct = 100.0 * done / expected
            filled = int(pct // 5)
            meter = "#" * filled + "." * (20 - filled)
            print(f"{group:<18}{done:>8}{expected:>8}  {meter} {pct:5.1f}%")
        else:
            print(f"{group:<18}{done:>8}{'?':>8}  (dataset not downloaded)")
    return done_total, expected_total


def report_errors(output_dir: Path) -> None:
    """Note how many permanent failures were recorded, if any."""
    errors_path = output_dir / "_errors.json"
    if not errors_path.exists():
        return
    try:
        errors = json.loads(errors_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    if errors:
        print(f"Errors   : {len(errors)} recorded in {errors_path}")


def main() -> int:
    """Print per-dimension progress for a benchmark run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pipeline", default=os.environ.get("BENCH_PIPELINE", "genieparse")
    )
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--pid-file", default="run.pid")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve() / args.pipeline
    data_dir = Path(args.data_dir).expanduser().resolve()

    pid = read_running_pid(Path(args.pid_file).expanduser().resolve())
    print(f"Pipeline : {args.pipeline}")
    print(f"Output   : {output_dir}")
    print(f"Run      : {'running, pid ' + str(pid) if pid else 'not running'}")
    print()

    if not output_dir.exists():
        print("No results yet — nothing has been run into this directory.")
        return 0

    done_total, expected_total = report_progress(output_dir, data_dir)

    print()
    if expected_total:
        remaining = max(expected_total - done_total, 0)
        print(f"Total    : {done_total}/{expected_total} pages, {remaining} remaining")
    else:
        print(f"Total    : {done_total} pages done")

    report_errors(output_dir)

    print()
    print("Re-running is resume: completed pages are skipped unless you pass --force.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
