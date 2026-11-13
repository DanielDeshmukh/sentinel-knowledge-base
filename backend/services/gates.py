from datetime import date
from typing import List, Tuple

from corpus.parser import CorpusMetadata, SYNTHETIC_LABEL, parse_corpus_record


def _metadata_from_mapping(metadata: dict | None) -> CorpusMetadata:
    values = metadata or {}
    raw_urls = values.get("source_urls", ())
    if isinstance(raw_urls, (tuple, list)):
        source_urls = tuple(raw_urls)
    elif isinstance(raw_urls, str):
        source_urls = (raw_urls,)
    else:
        source_urls = ()

    retrieved_at = values.get("retrieved_at")
    if isinstance(retrieved_at, str):
        try:
            retrieved_at = date.fromisoformat(retrieved_at)
        except ValueError:
            retrieved_at = None

    synthetic = values.get("synthetic", False)
    synthetic_label = values.get("synthetic_label")
    if synthetic is True and synthetic_label is None:
        synthetic_label = SYNTHETIC_LABEL

    return CorpusMetadata(
        title=values.get("title", ""),
        classification=values.get("classification", ""),
        source_urls=source_urls,
        retrieved_at=retrieved_at,
        reuse_basis=values.get("reuse_basis"),
        synthetic=synthetic,
        synthetic_label=synthetic_label,
    )


def run_gates(text: str, metadata: dict = None) -> Tuple[bool, List[dict]]:
    """Compatibility wrapper around the canonical corpus parser."""
    parsed = parse_corpus_record(
        text,
        _metadata_from_mapping(metadata),
        normalize_on_failure=False,
    )
    failures = [
        {
            "gate": issue.code,
            "name": issue.code,
            "message": issue.message,
            "line": issue.line,
        }
        for issue in parsed.final_diagnostics
    ]
    return parsed.valid, failures


def normalize_text(text: str, metadata: dict = None) -> str:
    """Normalize and recheck using the same parser and rules as corpus validation."""
    parsed = parse_corpus_record(
        text,
        _metadata_from_mapping(metadata),
        normalize_on_failure=True,
    )
    return parsed.markdown
