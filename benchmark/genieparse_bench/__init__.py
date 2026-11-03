"""ParseBench extension registering the GenieParse pipeline.

Importing this package registers the provider and its pipeline variants, so it
must be imported before the parse-bench CLI runs. `genieparse_bench.__main__`
does that; use `genieparse-bench` in place of `parse-bench`.
"""

from parse_bench.extensions import register_pipeline
from parse_bench.schemas.pipeline import PipelineSpec
from parse_bench.schemas.product import ProductType

from genieparse_bench.provider import GenieParseProvider
from genieparse_bench.runner import DEFAULT_PAGE_TIMEOUT_S

__all__ = ["GenieParseProvider"]

# Default: no LLM calls, matching the pipeline's own defaults.
register_pipeline(
    PipelineSpec(
        pipeline_name="genieparse",
        provider_name="genieparse",
        product_type=ProductType.PARSE,
        config={},
        per_file_timeout=DEFAULT_PAGE_TIMEOUT_S,
    )
)

# Figures and code blocks routed through GPT-4o Vision. Needs OPENAI_API_KEY,
# and bills one vision call per figure and code block across the whole run.
register_pipeline(
    PipelineSpec(
        pipeline_name="genieparse_llm",
        provider_name="genieparse",
        product_type=ProductType.PARSE,
        config={"process_code_llm": True, "process_figures_llm": True},
        per_file_timeout=DEFAULT_PAGE_TIMEOUT_S,
    )
)
