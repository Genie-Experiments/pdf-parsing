"""ParseBench provider backed by the GenieParse Dolphin pipeline."""

import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import markdown2
from parse_bench.inference.providers.base import (
    Provider,
    ProviderPermanentError,
    ProviderTransientError,
)
from parse_bench.inference.providers.registry import register_provider
from parse_bench.schemas.parse_output import PageIR, ParseOutput
from parse_bench.schemas.pipeline import PipelineSpec
from parse_bench.schemas.pipeline_io import (
    InferenceRequest,
    InferenceResult,
    RawInferenceResult,
)
from parse_bench.schemas.product import ProductType

from genieparse_bench.faults import describe_exit, is_transient
from genieparse_bench.runner import run_pipeline, sweep_stale_scratch

# Step 6 rewrites the pipeline's '---' page separators into numbered comments.
_PAGE_BREAK = re.compile(r"<!--\s*page_break_\d+\s*-->")


@register_provider("genieparse")
class GenieParseProvider(Provider):
    """Runs the 10-step Dolphin pipeline as a subprocess, one PDF per request."""

    def __init__(self, provider_name: str, base_config: dict[str, Any] | None = None):
        super().__init__(provider_name, base_config)
        # A killed run cannot clean up after itself, so reclaim its scratch here.
        sweep_stale_scratch()

    def run_inference(
        self, pipeline: PipelineSpec, request: InferenceRequest
    ) -> RawInferenceResult:
        if request.product_type != ProductType.PARSE:
            raise ProviderPermanentError(
                f"GenieParseProvider only supports PARSE, got {request.product_type}"
            )

        pdf_path = Path(request.source_file_path)
        if not pdf_path.exists():
            raise ProviderPermanentError(f"File not found: {pdf_path}")

        started_at = datetime.now()
        try:
            raw_output = run_pipeline(pdf_path, self.base_config)
        except subprocess.TimeoutExpired as e:
            # Treated as transient: a stuck page usually means the machine is
            # thrashing, and the retry may land when it is quieter.
            raise ProviderTransientError(
                f"Pipeline timed out after {e.timeout:.0f}s on {pdf_path.name}"
            ) from e
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "")[-2000:]
            message = (
                f"Pipeline {describe_exit(e.returncode)} on {pdf_path.name}: {stderr}"
            )
            if is_transient(e.returncode, e.stderr or ""):
                raise ProviderTransientError(message) from e
            raise ProviderPermanentError(message) from e
        except FileNotFoundError as e:
            raise ProviderPermanentError(str(e)) from e

        completed_at = datetime.now()
        return RawInferenceResult(
            request=request,
            pipeline=pipeline,
            pipeline_name=pipeline.pipeline_name,
            product_type=request.product_type,
            raw_output=raw_output,
            started_at=started_at,
            completed_at=completed_at,
            latency_in_ms=int((completed_at - started_at).total_seconds() * 1000),
        )

    def normalize(self, raw_result: RawInferenceResult) -> InferenceResult:
        markdown = raw_result.raw_output.get("markdown", "") or ""
        page_texts = [
            _markdown_tables_to_html(chunk) for chunk in _PAGE_BREAK.split(markdown)
        ]
        pages = [
            PageIR(page_index=index, markdown=text)
            for index, text in enumerate(page_texts)
        ]

        output = ParseOutput(
            task_type="parse",
            example_id=raw_result.request.example_id,
            pipeline_name=raw_result.pipeline_name,
            pages=pages,
            markdown="\n\n".join(page_texts),
        )
        return InferenceResult(
            request=raw_result.request,
            pipeline_name=raw_result.pipeline_name,
            product_type=raw_result.product_type,
            raw_output=raw_result.raw_output,
            output=output,
            started_at=raw_result.started_at,
            completed_at=raw_result.completed_at,
            latency_in_ms=raw_result.latency_in_ms,
        )


def _markdown_tables_to_html(content: str) -> str:
    """Render markdown tables as HTML.

    ParseBench scores tables with GriTS over HTML, but step 7 of the pipeline
    converts Dolphin's HTML tables into markdown. This converts them back; any
    HTML the pipeline left alone passes through untouched.
    """
    lines = content.split("\n")
    parts: list[str] = []
    table_lines: list[str] = []

    def flush() -> None:
        nonlocal table_lines
        if len(table_lines) >= 2:
            html = markdown2.markdown("\n".join(table_lines), extras=["tables"]).strip()
            if "<table>" in html.lower():
                parts.append(html)
            else:
                parts.extend(table_lines)
        else:
            parts.extend(table_lines)
        table_lines = []

    in_table = False
    for line in lines:
        if line.strip().startswith("|"):
            in_table = True
            table_lines.append(line)
        else:
            if in_table:
                flush()
                in_table = False
            parts.append(line)
    if in_table:
        flush()

    return "\n".join(parts)
