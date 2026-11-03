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

## Setup on a new machine

```bash
make bench-setup
```

Installs the pipeline (submodules, ML deps), downloads the ~770 MB Dolphin
weights into `pipeline/hf_model/`, and installs the benchmark package. On an
NVIDIA host run `make setup-pipeline-gpu` first — Dolphin uses CUDA when it is
available and CPU otherwise.

Then fetch the dataset:

```bash
make bench-download-test   # 12 PDFs, for a smoke test
make bench-download        # the full 2,078-page set
```

## 1. Calibrate — what will this cost here?

Dolphin inference is effectively the entire runtime, and it is hardware-bound,
so time a page before committing to a full run:

```bash
make bench-calibrate
make bench-calibrate RUNS=3 BENCH_CONCURRENCY=4
```

This reports the device Dolphin selected, seconds per page, and a projected
wall-clock time for the full benchmark, and writes `benchmark/calibration.json`.

Three things it will tell you that matter for planning:

- **Post-processing is free.** On an Apple M3, a dense page measured 81.2s of
  which Dolphin took 81.0s and all nine post-processing steps took 0.2s
  combined. Tune post-processing all you like; it costs nothing.
- **Page density matters more than page count.** The same M3 ran a ParseBench
  chart page in 45.4s and a dense two-column paper page in 81.2s, which is why
  calibrating on an actual dataset page beats estimating from any single sample.
- **Model load does not amortise.** The pipeline spawns one Dolphin subprocess
  per PDF, so every page reloads the model. Raising `BENCH_CONCURRENCY` is the
  only way to overlap that cost, and each worker holds its own copy of the
  model in memory.

Concurrency buys less than it looks on CPU. Dolphin is already multi-threaded,
so workers compete for the same cores: on the M3, three workers pushed per-page
latency from 45s to 89–115s, a throughput gain of roughly 1.4x rather than 3x.
Measure with `make bench-calibrate` at the concurrency you plan to use rather
than assuming it scales.

## 2. Smoke test

```bash
make bench-test
```

Runs the 12-page subset end to end. Do this before a full run — it catches a
broken provider in minutes rather than hours.

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
| Killed by SIGKILL/SIGTERM/SIGHUP/SIGINT/SIGBUS | transient | The OOM killer, a shutdown, or an operator — not the PDF's fault |
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
