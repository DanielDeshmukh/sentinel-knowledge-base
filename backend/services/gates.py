import re
from typing import Tuple, List

# Regex gates as defined in the spec
GATES = {
    "G1_Encoding": {
        "name": "Encoding Check",
        "description": "Valid UTF-8, no null bytes",
        "check": lambda text: "\x00" not in text,
        "message": "File contains null bytes or invalid encoding"
    },
    "G4_Control_Characters": {
        "name": "Control Characters",
        "description": "No control characters except newline and tab",
        "pattern": re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F]'),
        "check": lambda text: not re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F]').search(text),
        "message": "File contains control characters"
    },
    "G5_Structure": {
        "name": "Structure Check",
        "description": "Starts with a top-level heading",
        "check": lambda text: bool(re.match(r'^\s*# .+', text, re.MULTILINE)),
        "message": "Document must start with a top-level heading (#)"
    },
    "G6_Unsafe_Content": {
        "name": "Unsafe Content",
        "description": "No script tags or large embedded base64 blobs",
        "check": lambda text: "<script" not in text.lower() and not re.search(r'[A-Za-z0-9+/]{100,}={0,2}', text),
        "message": "File contains potentially unsafe content (script tags or large base64 blobs)"
    },
    "G7_Sensitive_Data": {
        "name": "Sensitive Data",
        "description": "No Aadhaar, PAN, API keys, or personal emails and phones",
        "patterns": [
            (re.compile(r'\b\d{4}\s?\d{4}\s?\d{4}\b'), "Aadhaar number"),
            (re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b'), "PAN number"),
            (re.compile(r'AKIA[0-9A-Z]{16}'), "AWS-style key"),
        ],
        "check": lambda text: not any(
            p.search(text) for p, _ in [
                (re.compile(r'\b\d{4}\s?\d{4}\s?\d{4}\b'), "Aadhaar number"),
                (re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b'), "PAN number"),
                (re.compile(r'AKIA[0-9A-Z]{16}'), "AWS-style key"),
            ]
        ),
        "message": "File contains sensitive data patterns"
    },
}

def run_gates(text: str, metadata: dict = None) -> Tuple[bool, List[dict]]:
    """
    Run all regex gates on the text.
    Returns (passed, failures) where failures is a list of {gate, message}.
    """
    failures = []

    for gate_id, gate in GATES.items():
        try:
            if not gate["check"](text):
                failures.append({
                    "gate": gate_id,
                    "name": gate["name"],
                    "message": gate["message"]
                })
        except Exception as e:
            failures.append({
                "gate": gate_id,
                "name": gate["name"],
                "message": f"Error checking gate: {str(e)}"
            })

    # G3: Metadata check
    if metadata:
        if not metadata.get("title"):
            failures.append({
                "gate": "G3_Metadata",
                "name": "Metadata Check",
                "message": "Title is required"
            })
        if not metadata.get("classification"):
            failures.append({
                "gate": "G3_Metadata",
                "name": "Metadata Check",
                "message": "Classification is required"
            })
        elif metadata.get("classification") not in ["public", "internal", "restricted"]:
            failures.append({
                "gate": "G3_Metadata",
                "name": "Metadata Check",
                "message": "Classification must be public, internal, or restricted"
            })

    passed = len(failures) == 0
    return passed, failures

def normalize_text(text: str, metadata: dict = None) -> str:
    """
    Normalize text for files that fail gates:
    - Strip control characters
    - Collapse whitespace
    - Fix heading levels
    - Insert missing metadata
    - Mask sensitive data
    """
    import unicodedata

    # Normalize Unicode (NFC)
    text = unicodedata.normalize("NFC", text)

    # Strip control characters except newline and tab
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', text)

    # Collapse stray whitespace
    text = re.sub(r'[^\S\n]+', ' ', text)

    # Mask sensitive data patterns
    text = re.sub(r'\b\d{4}\s?\d{4}\s?\d{4}\b', '[REDACTED-AADHAAR]', text)
    text = re.sub(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', '[REDACTED-PAN]', text)
    text = re.sub(r'AKIA[0-9A-Z]{16}', '[REDACTED-AWS-KEY]', text)

    # Insert missing metadata if needed
    lines = text.split('\n')
    header_lines = []

    if metadata and metadata.get("title"):
        header_lines.append(f"# {metadata['title']}")
    else:
        header_lines.append("# Untitled Document")

    if metadata and metadata.get("classification"):
        header_lines.append(f"\n> Classification: {metadata['classification']}")

    # Check if first non-empty line is a heading
    content_start = False
    for i, line in enumerate(lines):
        if line.strip():
            if not line.strip().startswith('#'):
                # Prepend header
                lines = header_lines + ["" if not header_lines else ""] + lines
            break

    return '\n'.join(lines)
