import unittest

from init_db import upgrade_corpus_schema


class RecordingConnection:
    def __init__(self):
        self.statements = []

    def execute(self, statement, parameters=None):
        self.statements.append((str(statement), parameters or {}))


class CorpusSchemaUpgradeTests(unittest.TestCase):
    def test_upgrade_adds_corpus_metadata_job_and_staging_job_link_idempotently(self):
        connection = RecordingConnection()

        upgrade_corpus_schema(connection)
        upgrade_corpus_schema(connection)

        sql = "\n".join(statement for statement, _ in connection.statements)
        self.assertIn("ALTER TABLE documents ADD COLUMN IF NOT EXISTS schema_version", sql)
        self.assertIn("ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_urls", sql)
        self.assertIn("ALTER TABLE documents ADD COLUMN IF NOT EXISTS markdown_content", sql)
        self.assertIn("ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_sha256", sql)
        self.assertIn("ALTER TABLE documents ADD COLUMN IF NOT EXISTS sync_state", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS corpus_ingestion_jobs", sql)
        self.assertIn("ALTER TABLE staging_chunks ADD COLUMN IF NOT EXISTS job_id", sql)
        self.assertIn("CREATE INDEX IF NOT EXISTS ix_corpus_jobs_admin", sql)
        ddl_statements = [
            statement for statement, _ in connection.statements
            if statement.lstrip().startswith(("ALTER TABLE", "CREATE TABLE", "CREATE INDEX"))
        ]
        self.assertTrue(all("IF NOT EXISTS" in statement for statement in ddl_statements))

    def test_job_status_values_are_constrained_and_document_has_searchable_default(self):
        from sqlalchemy import CheckConstraint
        from models.corpus_ingestion_job import CorpusIngestionJob
        from models.document import Document

        job_checks = " ".join(
            str(check.sqltext)
            for check in CorpusIngestionJob.__table__.constraints
            if isinstance(check, CheckConstraint)
        )
        document_checks = " ".join(
            str(check.sqltext)
            for check in Document.__table__.constraints
            if isinstance(check, CheckConstraint)
        )
        self.assertIn("'running'", job_checks)
        self.assertIn("'succeeded'", job_checks)
        self.assertIn("'failed'", job_checks)
        self.assertIn("'searchable'", document_checks)

        connection = RecordingConnection()
        upgrade_corpus_schema(connection)
        sql = "\n".join(statement for statement, _ in connection.statements)
        self.assertIn("DEFAULT 'searchable'", sql)
        self.assertIn("'searchable'", sql)


class CorpusModelShapeTests(unittest.TestCase):
    def test_document_declares_the_corpus_record_fields(self):
        from models.document import Document

        columns = Document.__table__.columns
        expected = {
            "schema_version", "origin", "manifest_path", "markdown_content",
            "content_sha256", "content_bytes", "media_type", "source_urls",
            "retrieved_at", "reuse_basis", "synthetic", "synthetic_label",
            "parser_version", "ruleset_version", "embedding_version",
            "embedding_dimension", "sync_state", "chunk_count", "vectors_written",
            "searchable_at", "updated_at",
        }
        self.assertTrue(expected.issubset(set(columns.keys())))

    def test_job_model_contains_progress_audit_and_safe_diagnostic_fields(self):
        from models.corpus_ingestion_job import CorpusIngestionJob

        columns = set(CorpusIngestionJob.__table__.columns.keys())
        self.assertTrue({
            "id", "document_id", "admin_id", "filename", "status", "stage",
            "sequence", "progress", "diagnostics", "error_code", "created_at",
            "started_at", "finished_at", "updated_at",
        }.issubset(columns))

    def test_job_response_exposes_safe_ordered_progress_and_diagnostics(self):
        from datetime import datetime
        from models.schemas import CorpusJobStatusResponse

        now = datetime(2026, 11, 13, 12, 0, 0)
        response = CorpusJobStatusResponse(
            id="job-1",
            document_id="doc-1",
            filename="owasp.md",
            status="running",
            stage="stage_vectors",
            sequence=4,
            progress={"vectors_written": 10, "total": 20},
            diagnostics=[{
                "code": "G7_EMAIL",
                "severity": "warning",
                "message": "Email address detected",
                "line": 2,
            }],
            error_code=None,
            created_at=now,
            started_at=now,
            finished_at=None,
            updated_at=now,
        )

        self.assertEqual(response.sequence, 4)
        self.assertEqual(response.progress["vectors_written"], 10)
        self.assertEqual(response.diagnostics[0].code, "G7_EMAIL")


if __name__ == "__main__":
    unittest.main()
