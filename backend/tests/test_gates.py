import unittest
from datetime import date

from corpus.parser import CorpusMetadata, parse_corpus_record
from services.gates import normalize_text, run_gates


class SharedGateTests(unittest.TestCase):
    def public_metadata(self):
        return {
            "title": "OWASP Top 10 Overview",
            "classification": "public",
            "source_urls": ["https://owasp.org/www-project-top-ten/"],
            "retrieved_at": date(2026, 11, 13),
            "reuse_basis": "Original public source summary.",
            "synthetic": False,
        }

    def test_ingestion_gate_uses_same_rule_code_and_safe_message_as_parser(self):
        sensitive_value = "reviewer@example.org"

        passed, failures = run_gates(
            f"# OWASP Top 10 Overview\n\n{ sensitive_value }",
            self.public_metadata(),
        )

        self.assertFalse(passed)
        self.assertIn("G7_EMAIL", {failure["gate"] for failure in failures})
        self.assertNotIn(sensitive_value, " ".join(failure["message"] for failure in failures))

    def test_ingestion_normalizer_uses_canonical_sensitive_redaction(self):
        normalized = normalize_text(
            "\ufeffBody with reviewer@example.org",
            self.public_metadata(),
        )

        self.assertTrue(normalized.startswith("# OWASP Top 10 Overview\n"))
        self.assertNotIn("reviewer@example.org", normalized)
        self.assertIn("[REDACTED-EMAIL]", normalized)

    def test_runtime_normalizer_matches_the_shared_parser_output(self):
        source = "\ufeffBody with reviewer@example.org"
        values = self.public_metadata()
        metadata = CorpusMetadata(
            title=values["title"],
            classification=values["classification"],
            source_urls=tuple(values["source_urls"]),
            retrieved_at=values["retrieved_at"],
            reuse_basis=values["reuse_basis"],
            synthetic=values["synthetic"],
        )

        expected = parse_corpus_record(source, metadata).markdown
        actual = normalize_text(source, values)

        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
