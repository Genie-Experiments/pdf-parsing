"""parse-bench CLI with the GenieParse pipelines registered."""

import sys

from parse_bench.cli import main as _parse_bench_main

# Imported for its side effect: it registers the provider and both pipelines.
import genieparse_bench  # noqa: F401  # pylint: disable=unused-import


def main() -> int:
    """Run the parse-bench CLI with GenieParse registered."""
    return _parse_bench_main()


if __name__ == "__main__":
    sys.exit(main())
