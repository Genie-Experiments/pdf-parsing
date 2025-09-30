import json
import re
import textwrap

def clean_and_format_code(raw_text: str) -> str:
    """
    Cleans and formats raw code/config snippets into a readable format.
    Handles:
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

    # --- 2. CLI configuration style ---
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

    # --- 3. CLI outputs (device prompt lines) ---
    if re.search(r"#\s*show\b", raw_text):
        return f"```\n{raw_text}\n```"

    # --- 4. HTTP request style ---
    if re.match(r"^(GET|POST|PUT|DELETE)\b", raw_text.strip(), re.I):
        return f"```\n{textwrap.dedent(raw_text)}\n```"

    # --- 5. Key-value or table dumps ---
    if re.search(r":", raw_text) or re.search(r"\s{2,}", raw_text):
        formatted = []
        for line in raw_text.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                formatted.append(f"{k.strip()}: {v.strip()}")
            else:
                formatted.append(line.strip())
        return f"```\n{chr(10).join(formatted)}\n```"

    # --- 6. Fallback: raw text with dedent ---
    return f"```\n{textwrap.dedent(raw_text)}\n```"

if __name__ == "__main__":
    
    example = "configure terminal\n\nvlan create 10 name DATA type port­mstprstp 0\n\nvlan create 20 name VOICE type port­mstprstp 0\n\nvlan create 30 name WIRELESS type port­mstprstp 0\n\nvlan i­sid 10 10\n\nvlan i­sid 20 20\n\nvlan i­sid 30 30\n\nvlan member add 10 1/1­1/4\n\nvlan member add 20 1/5­1/8\n\nvlan member add 30 1/9­1/11\n\nssh"


    code = clean_and_format_code(example)
    print(code)
