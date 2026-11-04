# ParseBench Integration

Scores the GenieParse pipeline against [ParseBench](https://www.parsebench.ai/),
LlamaIndex's open document-parsing benchmark: 2,078 human-verified pages from
1,211 enterprise documents, graded by ~169,000 deterministic rules across five
dimensions. Scoring is rule-based, not LLM-as-judge, so results are reproducible.

## How it fits together

`parse-bench` hands a provider one PDF and expects normalized markdown back.
`genieparse_bench` registers two pipeline variants against that interface:

| Pipeline | What it runs |
|----------|--------------|
| `genieparse` | The 10-step pipeline with its defaults — no LLM calls |
| `genieparse_llm` | Adds GPT-4o Vision on figures and code; needs `OPENAI_API_KEY` |

The provider shells out to `pipeline/main.py` using the pipeline's own virtualenv
rather than importing it, which keeps torch and transformers out of the
benchmark's dependency tree. Each page runs in its own temporary output
directory, because steps 2–10 write shared state under `_pipeline/`.

`genieparse-bench` is the `parse-bench` CLI with these pipelines registered —
every `parse-bench` subcommand works, so consult the upstream docs for anything
not covered here.

[`docs/how-it-works.html`](docs/how-it-works.html) draws the whole exchange as a
sequence diagram — open it in a browser. Violet lifelines are ours, green belong
to the ParseBench platform, and the single seam between them is the provider.
Its timings describe a 120s page. Hardware moves that number a lot — an M3 runs
these pages in 45s to 81s — but the split barely moves: Dolphin is ~98% of a
page wherever you run it.
[`docs/how-it-works.sequence.json`](docs/how-it-works.sequence.json) is the
source it was rendered from.

## Setup on a new machine

```bash
make bench-setup       # CPU — any Mac, or a Linux box with no NVIDIA card
make bench-setup-gpu   # NVIDIA GPU — same thing, CUDA build of torch
```

Both pull the submodules and ML deps, download the ~770 MB Dolphin weights into
`pipeline/hf_model/`, and install the benchmark package. They need
[uv](https://docs.astral.sh/uv/getting-started/installation/) and stop with
install instructions if it is missing. `make bench-setup-cpu` is an alias for
`make bench-setup`, for when a script should say which one it means.

`bench-setup-gpu` installs CUDA 12.4 wheels by default. Check what the driver
supports with `nvidia-smi` and override if it differs:

```bash
make bench-setup-gpu CUDA_VERSION=cu121
```

Then confirm it took:

```bash
make bench-device
```

That asks the pipeline's own torch what Dolphin will select, and prints `cuda`
or `cpu`. A `cpu` answer on a GPU machine means the CUDA wheels did not land —
much better caught here than inferred from a run going twenty times slower than
it should.

**Nothing after setup differs between CPU and GPU.** Dolphin picks CUDA when it
is available and CPU otherwise, so `bench-device`, `bench-calibrate`,
`bench-prewarm`, `bench-test` and `bench-run` are the same commands on both
machines. The only thing worth re-measuring per machine is concurrency.

The dataset lives outside git, and `make bench-calibrate` and `make bench-run`
fetch what they need the first time they are run, so neither needs a download
step in front of it. To pre-fetch it deliberately — on a metered connection, or
to warm a machine before a scheduled run:

```bash
make bench-download-test   # 12 PDFs, for a smoke test
make bench-download        # the full 2,078-page set
```

The automatic fetch only fires on an empty dataset directory, so downloading a
single dimension by hand is never undone by a later `make bench-run`.

## 1. Calibrate — what will this cost here?

Dolphin inference is effectively the entire runtime, and it is hardware-bound,
so time a page before committing to a full run:

```bash
make bench-calibrate
make bench-calibrate RUNS=3 BENCH_CONCURRENCY=4
```

It reports the device Dolphin selected, seconds per page, a projected
wall-clock time, and — when `BENCH_CONCURRENCY` is above 1 — a single-worker
baseline so the speedup figure means something. Results are written to
`benchmark/calibration.json`.

Three things it will tell you that matter for planning:

- **Post-processing is free.** On an Apple M3, a dense page measured 81.2s of
  which Dolphin took 81.0s and all nine post-processing steps took 0.2s
  combined. Tune post-processing all you like; it costs nothing.
- **Page density drives everything.** The same M3 ran a ParseBench chart page in
  45.4s and a dense two-column paper page in 81.2s. Calibrate on real dataset
  pages, which is what this command does by default.
- **Model load does not amortise by default.** The pipeline spawns one Dolphin
  subprocess per PDF, so every page pays a fresh cold start — 4.96s measured on
  an M3, of which importing torch and transformers is 4.26s and loading the
  398M-parameter weights only 0.18s. `make bench-prewarm` takes that out of the
  run; see below. Each concurrent worker also holds its own copy of the model.

### Concurrency is measured, not assumed

Measured on an 8-core M3 (4 performance, 4 efficiency) with 16 GB:

| Workers | Throughput | Versus 1 worker |
|---------|-----------|-----------------|
| 1 | 34-55s per page | baseline |
| 2 | 27.9s per page | 1.97x faster |
| 4 | 42.1s per page | **1.23x slower** |

Four workers lose to one. Each holds its own copy of the model, so past a
certain point they contend for cores and memory instead of overlapping. The
command warns when it measures that, and the right concurrency is whatever
measures fastest on the machine you are actually using — do not assume it
scales with core count.

Timings vary run to run with machine load, so treat a single number as a range.

## 2. Smoke test

```bash
make bench-test
```

Runs the 12-page subset end to end. Do this before a full run — it catches a
broken provider in minutes rather than hours. It writes to `output-test/` rather
than `output/`, so a smoke test can never seed the real run with results it
would then skip.

## 3. Full run

```bash
make bench-run
make bench-run BENCH_CONCURRENCY=4
make bench-run GROUP=table
```

Results land in `benchmark/output/<pipeline>/`: per-dimension HTML reports with
per-test-case drill-down, an aggregation dashboard, and CSV/JSON/Markdown
exports. `GROUP` scores one dimension at a time — `chart`, `table`, `layout`,
`text_content` or `text_formatting` — which lets you stop early or split a run
across machines.

View the reports (PDF rendering needs `http://`, not `file://`):

```bash
make bench-report
make bench-leaderboard
```

### Prewarming — take the model load out of the run

```bash
make bench-prewarm
make bench-prewarm CHUNK=100
```

Dolphin's CLI accepts a directory and processes it with one model load. This
feeds it the dataset in chunks and caches the output under
`benchmark/dolphin-cache/`; `make bench-run` then finds the cached page, skips
step 1, and starts at step 2.

Whether it is worth doing depends entirely on the hardware. The per-page cold
start is 4.96s on an M3 — `import torch` 1.20s, `import transformers` 3.06s,
the processor 0.45s, and the 398M-parameter weights only 0.18s. Those imports
cost the same wherever they run:

| | Cold start | Inference | Cold start as a share |
|---|---|---|---|
| CPU (M3) | 4.96s | ~16.6s | ~20% |
| GPU | 4.96s, plus CUDA init | much smaller | much larger |

On CPU this is a modest win. On a GPU it is the difference between the card
doing work and the card waiting for Python to finish importing — size a
hardware purchase without it and you are buying capacity to cover overhead.

Measured through the provider on one page: **1.62s cached against 42s
uncached**, because a prewarmed page skips inference entirely. That inference
is not free, it moved into the prewarm pass; what the cache removes from a
2,078-page run is 2,077 redundant model loads.

**Entries are keyed on PDF content, not filename.** parse-bench does not hand
the provider the dataset file — it materialises each example to a temporary
file with a generated name, `101cf170df9ba6d4-form.pdf` — so a name-keyed cache
would never match. Keying on the SHA-256 of the bytes also means two dataset
entries holding the same page are inferred once.

One consequence worth knowing about: Dolphin names figures after the input
file, and the markdown links to them by that name — and that markdown is the
text ParseBench scores. Cached output is therefore renamed back to the caller's
stem on the way out, links rewritten to match, so the result is byte-identical
to what inference would have produced. That equivalence is checked, not
assumed; see below.

Prewarming is safe to interrupt. Dolphin writes each page as it finishes, so a
killed pass loses only the page in flight — everything already cached stays,
and re-running re-chunks what is left. `CHUNK` therefore only trades model
loads against chunk granularity: at the default 50, a full run pays 42 loads
instead of 2,078.

To confirm the cache is not changing results on your own dataset, run the same
pages both ways and diff:

```bash
GENIEPARSE_USE_DOLPHIN_CACHE=0 make bench-run BENCH_OUTPUT=output-nocache
```

## 4. Surviving a long run

A full run is a day's work, so it is built to be interrupted. Inference writes
one `<example_id>.result.json` per page as it goes, and on the next run
parse-bench skips any page whose result file parses and carries both `request`
and `output`. That means:

- **Re-running is resuming.** `make bench-run` after a crash, a reboot or a
  killed SSH session picks up where it stopped. There is no separate resume
  command and no state to repair.
- **A half-written file is not trusted.** If the process died mid-write, the
  truncated JSON fails that check and the page is simply redone.
- **Failures leave no result file**, so a page that errored is retried on the
  next run. `make bench-retry-failed` is just a normal resume under a clearer
  name.
- **`--force` is the opposite of resume.** It regenerates everything. Only pass
  it when you have changed the pipeline and want fresh inference.

### Running detached

```bash
make bench-run-bg        # starts detached, survives logout
make bench-status        # pages done per dimension, and whether it is alive
make bench-watch         # follow the log
make bench-stop          # stop it; finished pages are kept
```

`bench-run-bg` writes `benchmark/run.pid` and appends to
`benchmark/logs/bench-<pipeline>.log`. It refuses to start a second run while
one is alive, so a stray repeat cannot have two writers in one output directory.
The run gets its own process group, so `bench-stop` signals the whole tree and
no orphaned Dolphin subprocess is left holding a CPU.
On a server you control, a systemd unit with `Restart=on-failure` running
`make bench-run` gives you the same thing plus automatic restart — resume makes
that safe.

### Retries

parse-bench retries transient and rate-limit failures five times with
exponential backoff (2s doubling to 32s), and retries a page twice more if it
exceeds the per-file timeout. What counts as transient is the provider's call,
so `genieparse_bench/faults.py` classifies pipeline failures:

| Failure | Classified | Why |
|---------|-----------|-----|
| Killed by SIGKILL/SIGTERM/SIGHUP/SIGBUS | transient | The OOM killer, a shutdown — not the PDF's fault |
| Killed by SIGINT | permanent | Someone pressed Ctrl-C; retrying would fight them |
| stderr shows memory or disk exhaustion | transient | The retry may land on a quieter machine |
| Page exceeds `GENIEPARSE_PAGE_TIMEOUT` (default 1200s) | transient | A stuck page usually means thrashing |
| Any other non-zero exit | permanent | The pipeline genuinely could not parse this page |

A permanent failure is recorded in `benchmark/output/<pipeline>/_errors.json`
and the run carries on to the next page.

### Scratch

Each page runs in its own scratch directory, because steps 2–10 write shared
state under `_pipeline/` that concurrent pages would otherwise overwrite. A
killed run cannot clean its own scratch up, so the provider sweeps anything
older than six hours on startup. Point `GENIEPARSE_SCRATCH_DIR` at a roomy disk
if `/tmp` is small — a full disk mid-run shows up as a transient failure on
every remaining page.

## 5. Iterate without re-running Dolphin

```bash
make bench-rescore
make bench-rescore GROUP=text_formatting
```

Re-scores saved inference output. Since post-processing costs ~0.2s per page,
this is the loop for tuning header/footer removal, section hierarchy and OCR
fixes against the benchmark — pay for inference once, then iterate for free.

## Known gaps

- **Visual grounding does not run.** The provider emits markdown only, so every
  layout example fails with `Inference output is not LayoutOutput and no
  provider adapter matched`. Dolphin's bounding boxes are in `recognition_json`,
  but mapping them onto ParseBench's `LayoutItemIR` needs page-dimension
  normalization that has not been written or validated yet. Treat Overall as
  covering four of five dimensions until this lands.
- **Charts will score poorly.** The pipeline does not extract chart data points;
  `genieparse_llm` sends figures to GPT-4o Vision but not as structured series
  and axis values, which is what the ChartDataPointMatch metric grades.
- **Heuristics are tuned on a different corpus.** Header/footer removal and
  section hierarchy were built against our own documents. ParseBench is
  insurance, finance and government. Misfires there are real signal.
- **The CUDA path has not been exercised.** `make bench-setup-gpu` installs a
  CUDA build and `make bench-device` reports what Dolphin sees, but no run has
  been measured on an NVIDIA machine. Treat the first GPU run as a trial:
  `make bench-device`, then `make bench-test`, before committing to a full pass.
- **Dolphin ignores Apple Silicon GPUs.** It selects CUDA or CPU only, so Macs
  run on CPU in float32 even where MPS is available. Changing that means a patch
  to the Dolphin submodule.

## Configuration

| Variable | Default | What it does |
|----------|---------|--------------|
| `BENCH_PIPELINE` | `genieparse` | Which variant to score |
| `BENCH_CONCURRENCY` | `1` | Pages in flight; each holds its own model copy |
| `BENCH_OUTPUT` | `output` | Results directory under `benchmark/` |
| `GROUP` | — | Score a single dimension |
| `RUNS` | `1` | Timed runs to average in calibration |
| `GENIEPARSE_PIPELINE_DIR` | `../pipeline` | Where `main.py` lives |
| `GENIEPARSE_PYTHON` | `../pipeline/.venv/bin/python` | Interpreter with the ML deps |
| `GENIEPARSE_PAGE_TIMEOUT` | `1200` | Seconds before a page counts as stuck |
| `GENIEPARSE_SCRATCH_DIR` | system temp | Where per-page scratch goes |
| `GENIEPARSE_DOLPHIN_CACHE` | `benchmark/dolphin-cache` | Where prewarmed Dolphin output lives |
| `GENIEPARSE_USE_DOLPHIN_CACHE` | `1` | Set to `0` to force inference per page, ignoring the cache |

## First measured results

From `make bench-test` — 12 pages, three per dimension. Far too small to rank
against the public leaderboard, but it shows the harness working and points at
where the pipeline actually stands.

| Dimension | Metric | Score |
|-----------|--------|-------|
| Tables | GriTS Con | 0.974 |
| Tables | GriTS TRM composite | 0.779 |
| Content faithfulness | Normalized text score | 0.896 |
| Semantic formatting | Normalized text score | 0.233 |
| Charts | Chart data point pass rate | 0.000 |
| Visual grounding | — | did not run |

Tables and content faithfulness look strong. Charts score zero as expected.
Semantic formatting is the interesting one: bold at 0.318 and titles at 0.278,
with underline, strikeout and highlight all at zero — the pipeline is dropping
inline emphasis that the markdown could carry. Header and footer rules also sit
at 0.000 under content faithfulness, which is worth a look given step 7 removes
headers and footers deliberately.

Re-scoring is free (`make bench-rescore`), so these are cheap to iterate on once
a full inference pass exists.
