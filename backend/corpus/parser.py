"""Canonical corpus metadata, normalization, and content validation."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import date
from typing import Literal
from urllib.parse import urlsplit


Classification = Literal["public", "internal", "restricted"]
DiagnosticSeverity = Literal["error", "warning"]
PARSER_VERSION = "1.0.0"
RULESET_VERSION = "2026-11-13.1"
SYNTHETIC_LABEL = "SYNTHETIC: for demonstration only"

CONTROL_CHARS = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
SCRIPT_TAG = re.compile(r"<\s*script\b", re.IGNORECASE)
LONG_BASE64 = re.compile(r"[A-Za-z0-9+/]{100,}={0,2}")
SENSITIVE_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "G7_AADHAAR",
        re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
        "Aadhaar-like number detected",
    ),
    (
        "G7_PAN",
        re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
        "PAN-like number detected",
    ),
    (
        "G7_AWS_KEY",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "AWS-style access key detected",
    ),
    (
        "G7_EMAIL",
        re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
        "Email address detected",
    ),
    (
        "G7_PHONE",
        re.compile(r"(?<!\d)(?:\+?91[\s.-]?)?[6-9]\d{9}(?!\d)"),
        "Indian phone number detected",
    ),
)


@dataclass(frozen=True)
class CorpusMetadata:
    title: str
    classification: Classification
    source_urls: tuple[str, ...] = ()
    retrieved_at: date | None = None
    reuse_basis: str | None = None
    synthetic: bool = False
    synthetic_label: str | None = None


@dataclass(frozen=True)
class CorpusDiagnostic:
    code: str
    severity: DiagnosticSeverity
    message: str
    line: int | None = None


@dataclass(frozen=True)
class ParsedCorpusRecord:
    metadata: CorpusMetadata
    markdown: str
    content_sha256: str
    parser_version: str
    ruleset_version: str
    normalized: bool
    diagnostics: tuple[CorpusDiagnostic, ...]
    final_diagnostics: tuple[CorpusDiagnostic, ...]

    @property
    def valid(self) -> bool:
        return not any(item.severity == "error" for item in self.final_diagnostics)


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_source_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _diagnostics(text: str, metadata: CorpusMetadata) -> tuple[CorpusDiagnostic, ...]:
    found: list[CorpusDiagnostic] = []

    def add(code: str, message: str, line: int | None = None) -> None:
        found.append(CorpusDiagnostic(code, "error", message, line))

    if "\x00" in text:
        add("G1_ENCODING", "Content contains a null byte", _line_of(text, text.index("\x00")))

    if not metadata.title.strip():
        add("G3_METADATA", "A non-empty title is required")
    elif "\n" in metadata.title or "\r" in metadata.title:
        add("G3_METADATA", "Title must be a single line")
    if metadata.classification not in ("public", "internal", "restricted"):
        add("G3_CLASSIFICATION", "Classification must be public, internal, or restricted")

    if CONTROL_CHARS.search(text):
        match = CONTROL_CHARS.search(text)
        add("G4_CONTROL", "Disallowed control characters detected", _line_of(text, match.start()))

    first_line_number = None
    first_line = None
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.strip():
            first_line_number, first_line = line_number, line
            break
    if first_line is None or not re.match(r"^#\s+\S", first_line):
        add("G5_HEADING", "The first non-empty line must be a level-one heading", first_line_number)

    body_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
        and not re.match(r"^#{1,6}\s", line.strip())
        and line.strip() != SYNTHETIC_LABEL
    ]
    if not body_lines:
        add("G5_CONTENT", "Document must contain content beyond headings and labels")

    script_match = SCRIPT_TAG.search(text)
    base64_match = LONG_BASE64.search(text)
    if script_match:
        add("G6_UNSAFE", "Script markup detected", _line_of(text, script_match.start()))
    if base64_match:
        add("G6_UNSAFE", "A long embedded base64 value was detected", _line_of(text, base64_match.start()))

    for code, pattern, message in SENSITIVE_PATTERNS:
        match = pattern.search(text)
        if match:
            add(code, message, _line_of(text, match.start()))

    if metadata.classification == "public":
        if metadata.synthetic is not False:
            add("G8_SYNTHETIC_FLAG", "Public source records must not be marked synthetic")
        if not metadata.source_urls or any(not url.strip() for url in metadata.source_urls):
            add("G8_PUBLIC_SOURCE", "At least one source URL is required for public records")
        elif any(not _valid_source_url(url) for url in metadata.source_urls):
            add("G8_PUBLIC_SOURCE_URL", "Source URLs must use HTTP or HTTPS and include a host")
        if not isinstance(metadata.retrieved_at, date):
            add("G8_RETRIEVED_AT", "A valid retrieval date is required for public records")
        if not _nonempty_text(metadata.reuse_basis):
            add("G8_REUSE_BASIS", "A reuse basis is required for public records")
    elif metadata.classification in ("internal", "restricted"):
        if metadata.synthetic is not True:
            add("G8_SYNTHETIC_FLAG", "Internal and restricted demo records must be synthetic")
        if metadata.source_urls:
            add("G8_SYNTHETIC_SOURCES", "Synthetic records must not list external source URLs")
        if metadata.retrieved_at is not None:
            add("G8_SYNTHETIC_RETRIEVED_AT", "Synthetic records must not have a source retrieval date")
        if not _nonempty_text(metadata.reuse_basis):
            add("G8_REUSE_BASIS", "A reuse basis is required for synthetic records")
        if metadata.synthetic_label != SYNTHETIC_LABEL:
            add("G9_SYNTHETIC_LABEL", "Synthetic records require the exact demonstration label")
        if SYNTHETIC_LABEL not in text:
            add("G9_SYNTHETIC_CONTENT_LABEL", "Content must include the exact demonstration label")
    elif metadata.synthetic_label is not None:
        add("G9_SYNTHETIC_LABEL", "Only synthetic records may declare a synthetic label")

    deduplicated: dict[tuple[str, int | None], CorpusDiagnostic] = {}
    for item in found:
        deduplicated[(item.code, item.line)] = item
    return tuple(deduplicated.values())


def _normalize(text: str, metadata: CorpusMetadata) -> str:
    normalized = unicodedata.normalize("NFC", text.lstrip("\ufeff"))
    normalized = CONTROL_CHARS.sub("", normalized)
    normalized = re.sub(r"[^\S\n]+", " ", normalized)

    for _code, pattern, _message in SENSITIVE_PATTERNS:
        replacement = {
            "G7_AADHAAR": "[REDACTED-AADHAAR]",
            "G7_PAN": "[REDACTED-PAN]",
            "G7_AWS_KEY": "[REDACTED-AWS-KEY]",
            "G7_EMAIL": "[REDACTED-EMAIL]",
            "G7_PHONE": "[REDACTED-PHONE]",
        }[_code]
        normalized = pattern.sub(replacement, normalized)

    nonempty_lines = [line for line in normalized.splitlines() if line.strip()]
    if not nonempty_lines or not re.match(r"^#\s+\S", nonempty_lines[0]):
        if metadata.title.strip():
            normalized = f"# {metadata.title.strip()}\n\n{normalized.lstrip()}"

    if metadata.classification in ("internal", "restricted") and metadata.synthetic:
        if SYNTHETIC_LABEL not in normalized:
            first_heading = re.search(r"(?m)^#\s+.+$", normalized)
            if first_heading:
                insert_at = first_heading.end()
                normalized = (
                    normalized[:insert_at]
                    + f"\n\n{SYNTHETIC_LABEL}"
                    + normalized[insert_at:]
                )

    return normalized


def parse_corpus_record(
    markdown: str,
    metadata: CorpusMetadata,
    *,
    normalize_on_failure: bool = True,
) -> ParsedCorpusRecord:
    source_metadata = metadata
    raw_urls = metadata.source_urls if isinstance(metadata.source_urls, (tuple, list)) else ()
    metadata = replace(
        metadata,
        title=metadata.title.strip() if isinstance(metadata.title, str) else "",
        source_urls=tuple(url.strip() if isinstance(url, str) else "" for url in raw_urls),
        reuse_basis=metadata.reuse_basis.strip()
        if isinstance(metadata.reuse_basis, str)
        else metadata.reuse_basis,
    )
    metadata_was_normalized = metadata != source_metadata
    initial = _diagnostics(markdown, metadata)
    normalized_markdown = _normalize(markdown, metadata) if initial and normalize_on_failure else markdown
    was_normalized = metadata_was_normalized or normalized_markdown != markdown
    final = _diagnostics(normalized_markdown, metadata) if was_normalized else initial
    unresolved_codes = {item.code for item in final}
    display_diagnostics = tuple(
        replace(item, severity="warning")
        if was_normalized and item.code not in unresolved_codes
        else item
        for item in initial
    )

    return ParsedCorpusRecord(
        metadata=metadata,
        markdown=normalized_markdown,
        content_sha256=hashlib.sha256(normalized_markdown.encode("utf-8")).hexdigest(),
        parser_version=PARSER_VERSION,
        ruleset_version=RULESET_VERSION,
        normalized=was_normalized,
        diagnostics=display_diagnostics,
        final_diagnostics=final,
    )
