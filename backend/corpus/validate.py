import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Dict, List, Mapping, Optional, Set

from corpus.parser import CorpusMetadata, SYNTHETIC_LABEL, parse_corpus_record


CLASSIFICATIONS = ("public", "internal", "restricted")
DEFAULT_COUNTS = {"public": 11, "internal": 8, "restricted": 6}


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


def _metadata_from_entry(entry: dict) -> CorpusMetadata:
    raw_urls = entry.get("source_urls")
    if isinstance(raw_urls, list):
        source_urls = tuple(value if isinstance(value, str) else "" for value in raw_urls)
    else:
        source_urls = ()

    raw_retrieved_at = entry.get("retrieved_at")
    retrieved_at = None
    if isinstance(raw_retrieved_at, str):
        try:
            candidate_date = date.fromisoformat(raw_retrieved_at)
            if candidate_date.isoformat() == raw_retrieved_at:
                retrieved_at = candidate_date
        except ValueError:
            pass

    synthetic = entry.get("synthetic")
    return CorpusMetadata(
        title=entry.get("title") if isinstance(entry.get("title"), str) else "",
        classification=entry.get("classification", ""),
        source_urls=source_urls,
        retrieved_at=retrieved_at,
        reuse_basis=entry.get("reuse_basis"),
        synthetic=synthetic,
        synthetic_label=SYNTHETIC_LABEL if synthetic is True else entry.get("synthetic_label"),
    )


def _diagnostic_suffix(code: str, classification: object) -> str:
    suffixes = {
        "G1_ENCODING": "encoding_invalid",
        "G3_METADATA": "title_missing",
        "G3_CLASSIFICATION": "classification_invalid",
        "G4_CONTROL": "control_characters_detected",
        "G5_HEADING": "h1_not_first",
        "G5_CONTENT": "content_missing",
        "G6_UNSAFE": "unsafe_content_detected",
        "G8_PUBLIC_SOURCE": "public_source_missing",
        "G8_PUBLIC_SOURCE_URL": "public_source_invalid",
        "G8_RETRIEVED_AT": "public_retrieval_date_invalid",
        "G8_REUSE_BASIS": (
            "public_reuse_basis_missing"
            if classification == "public"
            else "synthetic_reuse_basis_missing"
        ),
        "G8_SYNTHETIC_FLAG": "synthetic_flag_invalid",
        "G8_SYNTHETIC_SOURCES": "synthetic_source_urls_invalid",
        "G8_SYNTHETIC_RETRIEVED_AT": "synthetic_retrieval_date_invalid",
        "G9_SYNTHETIC_LABEL": "synthetic_label_missing",
        "G9_SYNTHETIC_CONTENT_LABEL": "synthetic_label_missing",
    }
    if code.startswith("G7_"):
        return f"sensitive_pattern_{code[3:].lower()}"
    return suffixes.get(code, f"parser_{code.lower()}")


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

        metadata = _metadata_from_entry(entry)
        parsed = parse_corpus_record(content, metadata, normalize_on_failure=False)
        for issue in parsed.final_diagnostics:
            suffix = _diagnostic_suffix(issue.code, classification)
            diagnostics.append(f"{path_text}:{suffix}")

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
