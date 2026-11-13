import unittest
from datetime import date

from corpus.parser import CorpusMetadata, parse_corpus_record


class CorpusParserTests(unittest.TestCase):
    def public_metadata(self, **overrides):
        values = {
            "title": "OWASP Top 10 Overview",
            "classification": "public",
            "source_urls": ("https://owasp.org/www-project-top-ten/",),
            "retrieved_at": date(2026, 11, 13),
            "reuse_basis": "Original summary of the public OWASP project page.",
            "synthetic": False,
            "synthetic_label": None,
        }
        values.update(overrides)
        return CorpusMetadata(**values)

    def synthetic_metadata(self, **overrides):
        values = {
            "title": "Synthetic Incident Response Example",
            "classification": "restricted",
            "source_urls": (),
            "retrieved_at": None,
            "reuse_basis": "Authored for this demonstration.",
            "synthetic": True,
            "synthetic_label": "SYNTHETIC: for demonstration only",
        }
        values.update(overrides)
        return CorpusMetadata(**values)

    def test_valid_public_record_preserves_provenance_and_hashes_markdown(self):
        markdown = "# OWASP Top 10 Overview\n\nA public source summary.\n"

        result = parse_corpus_record(markdown, self.public_metadata())

        self.assertTrue(result.valid)
        self.assertFalse(result.normalized)
        self.assertEqual(result.markdown, markdown)
        self.assertEqual(result.metadata.source_urls, ("https://owasp.org/www-project-top-ten/",))
        self.assertEqual(len(result.content_sha256), 64)
        self.assertTrue(result.parser_version)
        self.assertTrue(result.ruleset_version)

    def test_trims_provenance_fields_and_rejects_non_http_source_urls(self):
        metadata = self.public_metadata(
            title=" OWASP Top 10 Overview ",
            source_urls=(" https://owasp.org/www-project-top-ten/ ",),
            reuse_basis=" Original summary. ",
        )
        result = parse_corpus_record("# OWASP Top 10 Overview\n\nSummary", metadata)

        self.assertEqual(result.metadata.title, "OWASP Top 10 Overview")
        self.assertEqual(result.metadata.source_urls, ("https://owasp.org/www-project-top-ten/",))
        self.assertEqual(result.metadata.reuse_basis, "Original summary.")

        invalid = parse_corpus_record(
            "# OWASP Top 10 Overview\n\nSummary",
            self.public_metadata(source_urls=("ftp://example.org/corpus",)),
        )
        self.assertFalse(invalid.valid)
        self.assertIn("G8_PUBLIC_SOURCE_URL", {item.code for item in invalid.final_diagnostics})

        malformed = parse_corpus_record(
            "# OWASP Top 10 Overview\n\nSummary",
            self.public_metadata(source_urls=("http://[invalid",)),
            normalize_on_failure=False,
        )
        self.assertFalse(malformed.valid)
        self.assertIn("G8_PUBLIC_SOURCE_URL", {item.code for item in malformed.final_diagnostics})

    def test_public_provenance_failures_have_distinct_safe_rule_codes(self):
        result = parse_corpus_record(
            "# OWASP Top 10 Overview\n\nSummary",
            self.public_metadata(source_urls=(), retrieved_at=None, reuse_basis=""),
            normalize_on_failure=False,
        )

        self.assertFalse(result.valid)
        codes = {item.code for item in result.final_diagnostics}
        self.assertTrue({
            "G8_PUBLIC_SOURCE",
            "G8_RETRIEVED_AT",
            "G8_REUSE_BASIS",
        }.issubset(codes))

    def test_malformed_untrusted_metadata_returns_diagnostics_without_crashing(self):
        result = parse_corpus_record(
            "# OWASP Top 10 Overview\n\nSummary",
            self.public_metadata(synthetic=0, reuse_basis=["not text"]),
            normalize_on_failure=False,
        )

        self.assertFalse(result.valid)
        codes = {item.code for item in result.final_diagnostics}
        self.assertIn("G8_SYNTHETIC_FLAG", codes)
        self.assertIn("G8_REUSE_BASIS", codes)

    def test_synthetic_record_requires_exact_label_and_no_source_provenance(self):
        markdown = (
            "# Synthetic Incident Response Example\n\n"
            "SYNTHETIC: for demonstration only\n\n"
            "This example describes a simulated incident workflow.\n"
        )

        result = parse_corpus_record(markdown, self.synthetic_metadata())

        self.assertTrue(result.valid)
        invalid = parse_corpus_record(
            markdown,
            self.synthetic_metadata(synthetic_label="Synthetic demo"),
        )
        self.assertFalse(invalid.valid)
        self.assertIn("G9_SYNTHETIC_LABEL", {item.code for item in invalid.diagnostics})

    def test_rejects_invalid_classification_and_missing_title(self):
        result = parse_corpus_record(
            "# Example\n\nText",
            self.public_metadata(title="  ", classification="admin"),
        )

        self.assertFalse(result.valid)
        codes = {item.code for item in result.diagnostics}
        self.assertIn("G3_METADATA", codes)
        self.assertIn("G3_CLASSIFICATION", codes)

    def test_rejects_multiline_title_metadata(self):
        result = parse_corpus_record(
            "# OWASP Top 10 Overview\n\nSummary",
            self.public_metadata(title="OWASP Top 10\n# injected heading"),
            normalize_on_failure=False,
        )

        self.assertFalse(result.valid)
        self.assertIn("G3_METADATA", {item.code for item in result.final_diagnostics})

    def test_requires_first_nonempty_line_to_be_a_level_one_heading(self):
        result = parse_corpus_record(
            "Intro text\n\n# Example\n",
            self.public_metadata(),
            normalize_on_failure=False,
        )

        self.assertFalse(result.valid)
        diagnostic = next(item for item in result.diagnostics if item.code == "G5_HEADING")
        self.assertEqual(diagnostic.line, 1)

    def test_rejects_content_that_is_empty_after_the_title(self):
        result = parse_corpus_record("\n", self.public_metadata())

        self.assertFalse(result.valid)
        self.assertIn("G5_CONTENT", {item.code for item in result.final_diagnostics})

    def test_normalization_repairs_heading_controls_and_unicode(self):
        source = "\ufeffBody\x01 with Cafe\u0301\n"

        result = parse_corpus_record(source, self.public_metadata())

        self.assertTrue(result.valid)
        self.assertTrue(result.normalized)
        self.assertTrue(result.markdown.startswith("# OWASP Top 10 Overview\n"))
        self.assertIn("Café", result.markdown)
        self.assertNotIn("\x01", result.markdown)

    def test_masks_sensitive_values_and_diagnostics_never_echo_matches(self):
        secrets = ["1234 5678 9012", "ABCDE1234F", "AKIAIOSFODNN7EXAMPLE"]
        source = "# OWASP Top 10 Overview\n\n" + "\n".join(secrets)

        result = parse_corpus_record(source, self.public_metadata())

        self.assertTrue(result.valid)
        self.assertTrue(result.normalized)
        self.assertNotIn(secrets[0], result.markdown)
        self.assertNotIn(secrets[1], result.markdown)
        self.assertNotIn(secrets[2], result.markdown)
        diagnostic_text = " ".join(item.message for item in result.diagnostics)
        for value in secrets:
            self.assertNotIn(value, diagnostic_text)
        codes = {item.code for item in result.diagnostics}
        self.assertTrue({"G7_AADHAAR", "G7_PAN", "G7_AWS_KEY"}.issubset(codes))

    def test_persistent_unsafe_script_is_rejected_after_normalization(self):
        result = parse_corpus_record(
            "# OWASP Top 10 Overview\n\n<script>alert(1)</script>",
            self.public_metadata(),
        )

        self.assertFalse(result.valid)
        self.assertIn("G6_UNSAFE", {item.code for item in result.diagnostics})

    def test_null_byte_is_removed_but_long_base64_remains_a_blocking_error(self):
        null_result = parse_corpus_record(
            "# OWASP Top 10 Overview\n\nbody\x00text",
            self.public_metadata(),
        )
        self.assertTrue(null_result.valid)
        self.assertNotIn("\x00", null_result.markdown)
        self.assertIn("G1_ENCODING", {item.code for item in null_result.diagnostics})

        encoded = "A" * 120
        base64_result = parse_corpus_record(
            f"# OWASP Top 10 Overview\n\n{encoded}",
            self.public_metadata(),
        )
        self.assertFalse(base64_result.valid)
        self.assertIn("G6_UNSAFE", {item.code for item in base64_result.final_diagnostics})

    def test_sensitive_phone_and_email_patterns_are_reported_safely(self):
        values = ["person@example.test", "+91 9876543210"]
        result = parse_corpus_record(
            "# OWASP Top 10 Overview\n\n" + "\n".join(values),
            self.public_metadata(),
            normalize_on_failure=False,
        )

        self.assertFalse(result.valid)
        codes = {item.code for item in result.diagnostics}
        self.assertIn("G7_EMAIL", codes)
        self.assertIn("G7_PHONE", codes)
        diagnostic_text = " ".join(item.message for item in result.diagnostics)
        for value in values:
            self.assertNotIn(value, diagnostic_text)


if __name__ == "__main__":
    unittest.main()
