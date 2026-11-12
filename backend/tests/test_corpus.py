import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from corpus.validate import validate_corpus


SYNTHETIC_LABEL = "SYNTHETIC: for demonstration only"


class CorpusValidatorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "corpus"
        self.entries = []

        documents = {
            "public": ("public/summary.md", "# Public summary\n\nOriginal summary.\n"),
            "internal": (
                "internal/policy.md",
                f"# Internal policy\n\n> {SYNTHETIC_LABEL}\n\nProcedure.\n",
            ),
            "restricted": (
                "restricted/report.md",
                f"# Restricted report\n\n> {SYNTHETIC_LABEL}\n\nFinding.\n",
            ),
        }

        for classification, (relative_path, content) in documents.items():
            path = self.root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            self.entries.append({
                "path": relative_path,
                "title": path.stem,
                "classification": classification,
                "source_urls": (
                    ["https://example.com/source"] if classification == "public" else []
                ),
                "retrieved_at": "2026-11-13" if classification == "public" else None,
                "reuse_basis": "Original summary" if classification == "public"
                else "Original synthetic demonstration content",
                "synthetic": classification != "public",
            })

        self.write_manifest()

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_manifest(self):
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "manifest.json").write_text(
            json.dumps({"documents": self.entries}),
            encoding="utf-8",
        )

    def test_valid_fixture_has_no_issues(self):
        counts = {"public": 1, "internal": 1, "restricted": 1}
        self.assertEqual(validate_corpus(self.root, counts), [])

    def test_rejects_heading_after_document_text(self):
        path = self.root / "public/summary.md"
        path.write_text("Preamble\n\n# Public summary\n", encoding="utf-8")

        issues = validate_corpus(self.root, {"public": 1, "internal": 1, "restricted": 1})

        self.assertIn("public/summary.md:h1_not_first", issues)

    def test_requires_public_source_and_reuse_metadata(self):
        self.entries[0]["source_urls"] = []
        self.entries[0]["reuse_basis"] = ""
        self.write_manifest()

        issues = validate_corpus(self.root, {"public": 1, "internal": 1, "restricted": 1})

        self.assertIn("public/summary.md:public_source_missing", issues)
        self.assertIn("public/summary.md:public_reuse_basis_missing", issues)

    def test_requires_synthetic_flag_and_label(self):
        self.entries[1]["synthetic"] = False
        self.write_manifest()
        (self.root / "internal/policy.md").write_text(
            "# Internal policy\n\nProcedure.\n",
            encoding="utf-8",
        )

        issues = validate_corpus(self.root, {"public": 1, "internal": 1, "restricted": 1})

        self.assertIn("internal/policy.md:synthetic_flag_invalid", issues)
        self.assertIn("internal/policy.md:synthetic_label_missing", issues)

    def test_sensitive_pattern_diagnostics_never_echo_matched_values(self):
        sensitive_values = [
            "".join(str(digit % 10) for digit in range(12)),
            "ABCDE" + "".join(str(digit) for digit in range(1, 5)) + "F",
            "AKIA" + "".join(chr(code) for code in range(ord("A"), ord("Q"))),
            "reviewer" + "@" + "example.org",
            "+" + "91" + " " + "9" + "8765" + "43210",
        ]
        path = self.root / "public/summary.md"

        for sensitive_value in sensitive_values:
            path.write_text(
                f"# Public summary\n\n{sensitive_value}\n",
                encoding="utf-8",
            )
            issues = validate_corpus(
                self.root,
                {"public": 1, "internal": 1, "restricted": 1},
            )

            self.assertTrue(
                any(issue.startswith("public/summary.md:sensitive_pattern_") for issue in issues)
            )
            self.assertNotIn(sensitive_value, "\n".join(issues))

    def test_rejects_duplicate_and_unlisted_manifest_paths(self):
        self.entries.append(dict(self.entries[0]))
        orphan = self.root / "public/orphan.md"
        orphan.write_text("# Unlisted document\n", encoding="utf-8")
        self.write_manifest()

        issues = validate_corpus(self.root, {"public": 1, "internal": 1, "restricted": 1})

        self.assertIn("manifest.json:duplicate_path", issues)
        self.assertIn("public/orphan.md:unlisted_markdown", issues)

    def test_rejects_incorrect_classification_counts(self):
        issues = validate_corpus(
            self.root,
            {"public": 2, "internal": 1, "restricted": 1},
        )

        self.assertIn("manifest.json:classification_count_mismatch", issues)

    def test_module_cli_does_not_emit_runtime_warning(self):
        result = subprocess.run(
            [sys.executable, "-m", "corpus.validate", str(self.root)],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
        )

        self.assertNotIn("RuntimeWarning", result.stderr)


if __name__ == "__main__":
    unittest.main()
