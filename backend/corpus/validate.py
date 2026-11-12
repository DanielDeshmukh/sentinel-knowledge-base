import argparse
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Dict, List, Mapping, Optional, Set


CLASSIFICATIONS = ("public", "internal", "restricted")
DEFAULT_COUNTS = {"public": 11, "internal": 8, "restricted": 6}
SYNTHETIC_LABEL = "SYNTHETIC: for demonstration only"
SENSITIVE_PATTERNS = (
    re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"(?<!\d)(?:\+?91[\s.-]?)?[6-9]\d{9}(?!\d)"),
)


def _is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _safe_relative_path(value: object) -> Optional[PurePosixPath]:
    if not isinstance(value, str) or not value or "\\" in value:
        return None

    relative_path = PurePosixPath(value)
    if relative_path.is_absolute() or any(
        part in ("", ".", "..") for part in relative_path.parts
    ):
        return None
    if relative_path.suffix.lower() != ".md":
        return None
    return relative_path


def _has_sensitive_pattern(text: str) -> bool:
    return any(pattern.search(text) for pattern in SENSITIVE_PATTERNS)


def _has_first_level_heading(text: str) -> bool:
    for line in text.splitlines():
        if line.strip():
            return line.startswith("# ") and bool(line[2:].strip())
    return False


def _valid_iso_date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def validate_corpus(
    root: Path,
    expected_counts: Optional[Mapping[str, int]] = None,
) -> List[str]:
    diagnostics: List[str] = []
    root = Path(root)
    if not root.is_dir():
        return ["manifest.json:corpus_directory_missing"]

    manifest_path = root / "manifest.json"
    try:
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ["manifest.json:manifest_missing"]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ["manifest.json:manifest_unreadable"]

    if not isinstance(manifest_data, dict) or not isinstance(
        manifest_data.get("documents"), list
    ):
        return ["manifest.json:invalid_manifest_shape"]

    entries = manifest_data["documents"]
    listed_paths: Set[str] = set()
    classifications: Counter = Counter()

    for entry in entries:
        if not isinstance(entry, dict):
            diagnostics.append("manifest.json:invalid_entry")
            continue

        relative_path = _safe_relative_path(entry.get("path"))
        classification = entry.get("classification")
        if relative_path is None:
            diagnostics.append("manifest.json:invalid_path")
            continue

        path_text = relative_path.as_posix()
        if path_text in listed_paths:
            diagnostics.append("manifest.json:duplicate_path")
        listed_paths.add(path_text)

        if classification not in CLASSIFICATIONS:
            diagnostics.append(f"{path_text}:classification_invalid")
        else:
            classifications[classification] += 1
            if relative_path.parts[0] != classification:
                diagnostics.append(f"{path_text}:classification_path_mismatch")

        document_path = root.joinpath(*relative_path.parts)
        if not document_path.is_file():
            diagnostics.append(f"{path_text}:file_missing")
            continue

        try:
            content = document_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            diagnostics.append(f"{path_text}:file_unreadable")
            continue

        if not _has_first_level_heading(content):
            diagnostics.append(f"{path_text}:h1_not_first")
        if _has_sensitive_pattern(content):
            diagnostics.append(f"{path_text}:sensitive_pattern_detected")

        if not _is_nonempty_string(entry.get("title")):
            diagnostics.append(f"{path_text}:title_missing")

        source_urls = entry.get("source_urls")
        reuse_basis = entry.get("reuse_basis")
        synthetic = entry.get("synthetic")

        if classification == "public":
            if not isinstance(source_urls, list) or not any(
                _is_nonempty_string(url) for url in source_urls
            ):
                diagnostics.append(f"{path_text}:public_source_missing")
            if not _valid_iso_date(entry.get("retrieved_at")):
                diagnostics.append(f"{path_text}:public_retrieval_date_invalid")
            if not _is_nonempty_string(reuse_basis):
                diagnostics.append(f"{path_text}:public_reuse_basis_missing")
            if synthetic is not False:
                diagnostics.append(f"{path_text}:synthetic_flag_invalid")
        elif classification in ("internal", "restricted"):
            if synthetic is not True:
                diagnostics.append(f"{path_text}:synthetic_flag_invalid")
            if SYNTHETIC_LABEL not in content:
                diagnostics.append(f"{path_text}:synthetic_label_missing")
            if source_urls != []:
                diagnostics.append(f"{path_text}:synthetic_source_urls_invalid")
            if entry.get("retrieved_at") is not None:
                diagnostics.append(f"{path_text}:synthetic_retrieval_date_invalid")
            if not _is_nonempty_string(reuse_basis):
                diagnostics.append(f"{path_text}:synthetic_reuse_basis_missing")

    actual_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*.md")
        if path.is_file()
    }
    for path_text in actual_paths - listed_paths:
        diagnostics.append(f"{path_text}:unlisted_markdown")

    requested_counts = DEFAULT_COUNTS if expected_counts is None else expected_counts
    if set(requested_counts) - set(CLASSIFICATIONS):
        diagnostics.append("manifest.json:invalid_expected_counts")
    elif any(
        not isinstance(requested_counts.get(classification, 0), int)
        or requested_counts.get(classification, 0) < 0
        or classifications.get(classification, 0)
        != requested_counts.get(classification, 0)
        for classification in CLASSIFICATIONS
    ):
        diagnostics.append("manifest.json:classification_count_mismatch")

    return sorted(set(diagnostics))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate evaluator corpus metadata and content.")
    parser.add_argument(
        "corpus_dir",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="corpus directory (defaults to the directory containing this module)",
    )
    args = parser.parse_args()

    diagnostics = validate_corpus(args.corpus_dir)
    for diagnostic in diagnostics:
        print(diagnostic)
    return 1 if diagnostics else 0


if __name__ == "__main__":
    sys.exit(main())
