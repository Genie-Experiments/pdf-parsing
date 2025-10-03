import json
import re
import textwrap

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
    raw_text = raw_text.strip()

    # --- 1. JSON-like fragments ---
    candidate = raw_text.replace("(", "{").replace(")", "}")
    candidate = candidate.replace("'", '"')  # normalize quotes
    candidate = candidate.replace('""', '"')

    common_fixes = {
        "ash-key": "ssh-key",
        "assword-encrypted": "password-encrypted",
        "rsaward-encrypted": "password-encrypted",
        "rofile": "profile",
        "rda": "role"
    }
    for bad, good in common_fixes.items():
        candidate = candidate.replace(bad, good)

    candidate = re.sub(r'(\w+)=([\w\-]+)', r'\1-\2', candidate)  # in=crc-errors → in-crc-errors
    candidate = re.sub(r",\s*([}\]])", r"\1", candidate)  # fix dangling commas

    try:
        obj = json.loads(candidate)
        return f"```\n{json.dumps(obj, indent=2)}\n```"
    except Exception:
        pass  # keep going if not valid JSON

    # --- 2. Python code ---
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
    
    if (re.search(python_keywords, raw_text, re.I) or 
        any(re.search(pattern, raw_text, re.MULTILINE) for pattern in python_patterns)):
        
        # Clean and format Python code with smart indentation inference
        lines = [line.rstrip() for line in raw_text.splitlines()]
        
        # Check if we have existing indentation or need to infer it
        has_existing_indent = any(line.startswith(' ') or line.startswith('\t') for line in lines if line.strip())
        
        if has_existing_indent:
            # Use existing indentation logic
            line_info = []
            for line in lines:
                if line.strip():
                    leading_spaces = len(line) - len(line.lstrip())
                    line_info.append((leading_spaces, line.strip()))
                else:
                    line_info.append((None, ""))
            
            if line_info:
                min_indent = min(spaces for spaces, content in line_info if spaces is not None and content)
                formatted_lines = []
                for spaces, content in line_info:
                    if spaces is None:
                        formatted_lines.append("")
                    elif not content:
                        formatted_lines.append("")
                    else:
                        relative_indent = max(0, spaces - min_indent)
                        indent_level = relative_indent // 4
                        if relative_indent % 4 > 0:
                            indent_level += 1
                        formatted_lines.append("    " * indent_level + content)
            else:
                formatted_lines = lines
        else:
            # Infer indentation based on Python syntax patterns
            formatted_lines = []
            indent_stack = [0]  # Stack to track indentation levels
            
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                if not line_stripped:
                    formatted_lines.append("")
                    continue
                
                current_indent = indent_stack[-1]
                
                # Dedenting keywords (except, elif, else, finally)
                if re.match(r'^(except|elif|else|finally):', line_stripped):
                    if len(indent_stack) > 1:
                        indent_stack.pop()  # Go back one level
                    current_indent = indent_stack[-1]
                
                # Block-ending statements that should cause dedent for following lines
                elif re.match(r'^(continue|break|pass)$', line_stripped):
                    # These end the current block, apply current indent then prepare for dedent
                    formatted_lines.append("    " * current_indent + line_stripped)
                    # Check if next line should be dedented
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if (next_line and 
                            not re.match(r'^(except|elif|else|finally|class|def):', next_line) and
                            not re.match(r'^(continue|break|pass|return)\b', next_line)):
                            # Next line should be dedented
                            if len(indent_stack) > 1:
                                indent_stack.pop()
                    continue
                
                # Return statements - usually at function body level
                elif re.match(r'^return\b', line_stripped):
                    # Return should typically be at the function body level
                    # Try to dedent to appropriate level
                    target_indent = max(0, current_indent - 1) if current_indent > 1 else current_indent
                    formatted_lines.append("    " * target_indent + line_stripped)
                    continue
                
                # Apply current indentation
                formatted_lines.append("    " * current_indent + line_stripped)
                
                # Increase indent for lines ending with ':'
                if line_stripped.endswith(':'):
                    new_indent = current_indent + 1
                    indent_stack.append(new_indent)
        
        # Remove excessive blank lines (more than 2 consecutive)
        clean_lines = []
        blank_count = 0
        for line in formatted_lines:
            if not line.strip():
                blank_count += 1
                if blank_count <= 2:
                    clean_lines.append(line)
            else:
                blank_count = 0
                clean_lines.append(line)
        
        return f"```python\n{chr(10).join(clean_lines)}\n```"

    # --- 3. CLI configuration style ---
    if re.search(r"\b(configure terminal|interface|router|ip address|vlan|spbm)\b", raw_text, re.I):
        formatted_lines = []
        indent = 0
        for line in raw_text.splitlines():
            line_stripped = line.strip()
            if not line_stripped:
                continue
            if re.match(r"^(exit|end)$", line_stripped, re.I):
                indent = max(indent - 1, 0)
            formatted_lines.append("  " * indent + line_stripped)
            if re.match(r"^(configure terminal|interface|router|vlan|spbm)\b", line_stripped, re.I):
                indent += 1
        return f"```\n{chr(10).join(formatted_lines)}\n```"

    # --- 4. CLI outputs (device prompt lines) ---
    if re.search(r"#\s*show\b", raw_text):
        return f"```\n{raw_text}\n```"

    # --- 5. HTTP request style ---
    if re.match(r"^(GET|POST|PUT|DELETE)\b", raw_text.strip(), re.I):
        return f"```\n{textwrap.dedent(raw_text)}\n```"

    # --- 6. Key-value or table dumps ---
    # Only apply this if it's not Python code (avoid breaking Python with colons)
    if (re.search(r":", raw_text) or re.search(r"\s{2,}", raw_text)) and not re.search(python_keywords, raw_text, re.I):
        formatted = []
        for line in raw_text.splitlines():
            if ":" in line and not re.search(r"^\s*(if|elif|else|for|while|try|except|finally|with|def|class).*:", line):
                # Only split on colon if it's not a Python control structure
                k, v = line.split(":", 1)
                formatted.append(f"{k.strip()}: {v.strip()}")
            else:
                formatted.append(line.strip())
        return f"```\n{chr(10).join(formatted)}\n```"

    # --- 7. Fallback: raw text with dedent ---
    return f"```\n{textwrap.dedent(raw_text)}\n```"