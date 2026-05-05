import json
import re
import textwrap
from typing import List, Optional

from utils.logger import get_logger


def _wrap_in_markdown(content: str, language: str = "") -> str:
    """Wrap content in markdown code blocks."""
    return f"```{language}\n{content}\n```"


def _try_format_as_json(text: str) -> Optional[str]:
    """Attempt to format text as JSON. Returns None if not valid JSON."""
    logger = get_logger(__name__)

    # Normalize common issues
    candidate = text.replace("'", '"')  # normalize quotes
    candidate = candidate.replace('""', '"')

    # Apply common OCR fixes
    common_fixes = {
        "ash-key": "ssh-key",
        "assword-encrypted": "password-encrypted",
        "rsaward-encrypted": "password-encrypted",
        "rofile": "profile",
        "rda": "role",
    }
    for bad, good in common_fixes.items():
        candidate = candidate.replace(bad, good)

    # Fix common patterns
    candidate = re.sub(
        r"(\w+)=([\w\-]+)", r"\1-\2", candidate
    )  # in=crc-errors → in-crc-errors
    candidate = re.sub(r",\s*([}\]])", r"\1", candidate)  # fix dangling commas

    try:
        obj = json.loads(candidate)
        logger.debug("Successfully formatted as JSON")
        return _wrap_in_markdown(json.dumps(obj, indent=2), "json")
    except Exception:
        logger.debug("Text is not valid JSON")
        return None


def _is_python_code(text: str) -> bool:
    """Check if text appears to be Python code."""
    python_keywords = r"\b(def|class|import|from|if|elif|else|for|while|try|except|finally|with|return|yield|lambda|async|await|print)\b"
    python_patterns = [
        r"^\s*(def|class)\s+\w+",  # function/class definitions
        r"^\s*(import|from)\s+\w+",  # import statements
        r"^\s*(if|elif|else|for|while|try|except|finally|with)\s*.*:",  # control structures
        r"^\s*@\w+",  # decorators
        r"^\s*#.*",  # comments
        r"print\s*\(",  # print statements
        r"=\s*\[.*\]|=\s*\{.*\}",  # list/dict assignments
    ]

    return re.search(python_keywords, text, re.I) or any(
        re.search(pattern, text, re.MULTILINE) for pattern in python_patterns
    )


def _normalize_existing_indentation(lines: List[str]) -> List[str]:
    """Normalize existing indentation in code lines."""
    line_info = []
    for line in lines:
        if line.strip():
            leading_spaces = len(line) - len(line.lstrip())
            line_info.append((leading_spaces, line.strip()))
        else:
            line_info.append((None, ""))

    if not line_info:
        return lines

    # Find minimum indentation (excluding empty lines)
    valid_indents = [
        spaces for spaces, content in line_info if spaces is not None and content
    ]
    if not valid_indents:
        return lines

    min_indent = min(valid_indents)

    # Detect the indentation unit used by the source (2, 4, or tab-equivalent spaces).
    # Use the smallest non-zero relative indent we can find — that's one indent level.
    relative_indents = sorted(
        {
            max(0, s - min_indent)
            for s, c in line_info
            if s is not None and c and s > min_indent
        }
    )
    indent_unit = relative_indents[0] if relative_indents else 4
    indent_unit = max(1, indent_unit)  # guard against degenerate input

    # Normalize indentation
    formatted_lines = []
    for spaces, content in line_info:
        if spaces is None:
            formatted_lines.append("")
        elif not content:
            formatted_lines.append("")
        else:
            relative_indent = max(0, spaces - min_indent)
            indent_level = round(relative_indent / indent_unit)
            formatted_lines.append("    " * indent_level + content)

    return formatted_lines


def _infer_python_indentation(lines: List[str]) -> List[str]:
    """Infer indentation for Python code based on syntax patterns."""
    formatted_lines = []
    indent_stack = [0]  # Stack to track indentation levels

    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped:
            formatted_lines.append("")
            continue

        current_indent = indent_stack[-1]

        # Handle dedenting keywords (except, elif, else, finally)
        if re.match(r"^(except|elif|else|finally):", line_stripped):
            if len(indent_stack) > 1:
                indent_stack.pop()  # Go back one level
            current_indent = indent_stack[-1]

        # Handle block-ending statements that should cause dedent for following lines
        elif re.match(r"^(continue|break|pass)$", line_stripped):
            # These end the current block, apply current indent then prepare for dedent
            formatted_lines.append("    " * current_indent + line_stripped)
            # Check if next line should be dedented
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if (
                    next_line
                    and not re.match(
                        r"^(except|elif|else|finally|class|def):", next_line
                    )
                    and not re.match(r"^(continue|break|pass|return)\b", next_line)
                ):
                    # Next line should be dedented
                    if len(indent_stack) > 1:
                        indent_stack.pop()
            continue

        # `return` stays at the current indent level — dedenting it blindly would
        # break nested returns (e.g., inside an if-block inside a function).

        # Apply current indentation
        formatted_lines.append("    " * current_indent + line_stripped)

        # Increase indent for lines ending with ':'
        if line_stripped.endswith(":"):
            new_indent = current_indent + 1
            indent_stack.append(new_indent)

    return formatted_lines


def _remove_excessive_blank_lines(
    lines: List[str], max_consecutive: int = 2
) -> List[str]:
    """Remove excessive consecutive blank lines."""
    clean_lines = []
    blank_count = 0

    for line in lines:
        if not line.strip():
            blank_count += 1
            if blank_count <= max_consecutive:
                clean_lines.append(line)
        else:
            blank_count = 0
            clean_lines.append(line)

    return clean_lines


def _format_python_code(text: str) -> str:
    """Format Python code with smart indentation inference."""
    logger = get_logger(__name__)
    logger.debug("Formatting Python code")

    lines = [line.rstrip() for line in text.splitlines()]

    # Check if we have existing indentation or need to infer it
    has_existing_indent = any(
        line.startswith(" ") or line.startswith("\t") for line in lines if line.strip()
    )

    if has_existing_indent:
        formatted_lines = _normalize_existing_indentation(lines)
    else:
        formatted_lines = _infer_python_indentation(lines)

    # Remove excessive blank lines
    clean_lines = _remove_excessive_blank_lines(formatted_lines)

    return _wrap_in_markdown("\n".join(clean_lines), "python")


def _is_cli_config(text: str) -> bool:
    """Check if text appears to be CLI configuration."""
    return bool(
        re.search(
            r"\b(configure terminal|interface|router|ip address|vlan|spbm)\b",
            text,
            re.I,
        )
    )


def _format_cli_config(text: str) -> str:
    """Format CLI configuration with hierarchical indentation."""
    logger = get_logger(__name__)
    logger.debug("Formatting CLI configuration")

    formatted_lines = []
    indent = 0

    for line in text.splitlines():
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # Handle exit commands
        if re.match(r"^(exit|end)$", line_stripped, re.I):
            indent = max(indent - 1, 0)

        # Apply indentation
        formatted_lines.append("  " * indent + line_stripped)

        # Increase indent for configuration blocks
        if re.match(
            r"^(configure terminal|interface|router|vlan|spbm)\b", line_stripped, re.I
        ):
            indent += 1

    return _wrap_in_markdown("\n".join(formatted_lines))


def _is_cli_output(text: str) -> bool:
    """Check if text appears to be CLI command output."""
    return bool(re.search(r"#\s*show\b", text))


def _is_http_request(text: str) -> bool:
    """Check if text appears to be an HTTP request."""
    return bool(re.match(r"^(GET|POST|PUT|DELETE)\b", text.strip(), re.I))


def _is_key_value_content(text: str) -> bool:
    """Check if text appears to be key-value pairs (avoiding Python code)."""
    # Avoid Python code (which also has colons)
    python_keywords = (
        r"\b(def|class|import|from|if|elif|else|for|while|try|except|finally|with)\b"
    )
    if re.search(python_keywords, text, re.I):
        return False

    # Check for key-value patterns
    return bool(re.search(r":", text) or re.search(r"\s{2,}", text))


def _format_key_value_content(text: str) -> str:
    """Format key-value pair content."""
    logger = get_logger(__name__)
    logger.debug("Formatting key-value content")

    formatted = []
    for line in text.splitlines():
        line_stripped = line.strip()
        if not line_stripped:
            formatted.append("")
            continue

        # Format key-value pairs (avoid Python syntax)
        if ":" in line_stripped and not re.search(
            r"^\s*(if|elif|else|for|while|try|except|finally|with|def|class).*:",
            line_stripped,
        ):
            parts = line_stripped.split(":", 1)
            if len(parts) == 2:
                key, value = parts
                formatted.append(f"{key.strip()}: {value.strip()}")
            else:
                formatted.append(line_stripped)
        else:
            formatted.append(line_stripped)

    return _wrap_in_markdown("\n".join(formatted))


def clean_and_format_code(raw_text: str) -> str:
    """
    Cleans and formats raw code/config snippets into a readable format.

    Handles:
      - Python code (with smart indentation inference)
      - JSON-like fragments
      - CLI configs (hierarchical)
      - CLI command outputs (device# show ...)
      - Plain text tables / key-value dumps
      - HTTP requests

    NOTHING is dropped: if parsing fails, raw text is returned intact
    with only spacing normalized.

    Always wraps output in triple backticks for markdown rendering.
    """
    logger = get_logger(__name__)

    if not raw_text or not raw_text.strip():
        return _wrap_in_markdown("")

    text = raw_text.strip()
    logger.debug("Formatting code snippet (length: %d)", len(text))

    # Try formatters in order of specificity

    # 1. Try JSON formatting first
    json_result = _try_format_as_json(text)
    if json_result:
        return json_result

    # 2. Check for Python code
    if _is_python_code(text):
        return _format_python_code(text)

    # 3. Check for CLI configuration
    if _is_cli_config(text):
        return _format_cli_config(text)

    # 4. Check for CLI output
    if _is_cli_output(text):
        logger.debug("Formatting as CLI output")
        return _wrap_in_markdown(text)

    # 5. Check for HTTP requests
    if _is_http_request(text):
        logger.debug("Formatting as HTTP request")
        return _wrap_in_markdown(textwrap.dedent(text), "http")

    # 6. Check for key-value content
    if _is_key_value_content(text):
        return _format_key_value_content(text)

    # 7. Fallback: raw text with dedent
    logger.debug("Using fallback formatting")
    return _wrap_in_markdown(textwrap.dedent(text))
