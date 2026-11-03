"""Telling retryable pipeline failures apart from real ones.

parse-bench retries ProviderTransientError and ProviderRateLimitError with
exponential backoff, and gives up immediately on ProviderPermanentError. Over a
multi-hour local run most failures are environmental — the OOM killer, a full
disk, a shutdown signal — and are worth another attempt on a quieter machine.
A PDF the pipeline genuinely cannot parse is not.
"""

import signal

# Signals that mean "something outside the pipeline killed it": the OOM killer,
# a system shutdown, an operator stopping the run.
_TRANSIENT_SIGNALS = {
    signal.SIGKILL,
    signal.SIGTERM,
    signal.SIGHUP,
    signal.SIGBUS,
}

# SIGINT is deliberately absent: it means someone pressed Ctrl-C, and retrying
# five times with backoff would fight them for half a minute.

# Substrings in stderr that point at resource exhaustion rather than bad input.
_TRANSIENT_MARKERS = (
    "out of memory",
    "outofmemoryerror",
    "cannot allocate memory",
    "can't allocate memory",
    "defaultcpuallocator",
    "no space left on device",
    "resource temporarily unavailable",
    "too many open files",
    "connection reset",
    "connection refused",
    "temporary failure in name resolution",
)


def is_transient(returncode: int, stderr: str) -> bool:
    """True when a failed pipeline run is worth retrying."""
    if returncode < 0 and -returncode in {s.value for s in _TRANSIENT_SIGNALS}:
        return True
    # Shells report a signal death as 128 + signal number.
    if returncode > 128 and (returncode - 128) in {s.value for s in _TRANSIENT_SIGNALS}:
        return True

    haystack = (stderr or "").lower()
    return any(marker in haystack for marker in _TRANSIENT_MARKERS)


def describe_exit(returncode: int) -> str:
    """Human-readable exit status, naming the signal where there was one."""
    if returncode < 0:
        try:
            return f"killed by {signal.Signals(-returncode).name}"
        except ValueError:
            return f"killed by signal {-returncode}"
    if returncode > 128:
        try:
            return f"killed by {signal.Signals(returncode - 128).name}"
        except ValueError:
            return f"exited {returncode}"
    return f"exited {returncode}"
