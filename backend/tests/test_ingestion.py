import io
import unittest
from datetime import date
from unittest.mock import patch

from corpus.parser import CorpusMetadata
from models.chunk import Chunk, StagingChunk
from services.embedding import EmbeddingServiceUnavailable
from services.ingestion import process_ingestion


class FakeUpload:
    def __init__(self, filename, content, content_type="text/markdown"):
        self.filename = filename
        self.content_type = content_type
        self.file = io.BytesIO(content)


class FakeQuery:
    def __init__(self, model, db):
        self.model = model
        self.db = db

    def filter(self, *_args):
        return self

    def all(self):
        if self.model is StagingChunk:
            return list(self.db.staging_chunks)
        return []

    def delete(self, **_kwargs):
        if self.model is StagingChunk:
            count = len(self.db.staging_chunks)
            self.db.staging_chunks.clear()
            return count
        return 0


class FakeSession:
    def __init__(self):
        self.documents = []
        self.staging_chunks = []
        self.chunks = []
        self.commits = 0
        self.rollbacks = 0
        self.fail_on_commit = None

    def add(self, value):
        if isinstance(value, Chunk):
            self.chunks.append(value)
        elif isinstance(value, StagingChunk):
            self.staging_chunks.append(value)
        else:
            self.documents.append(value)

    def add_all(self, values):
        for value in values:
            self.add(value)

    def flush(self):
        pass

    def commit(self):
        self.commits += 1
        if self.fail_on_commit == self.commits:
            self.chunks.clear()
            raise RuntimeError("simulated production transaction failure")

    def rollback(self):
        self.rollbacks += 1

    def query(self, model):
        return FakeQuery(model, self)


class CorpusIngestionTests(unittest.TestCase):
    def setUp(self):
        self.metadata = CorpusMetadata(
            title="OWASP Top 10 Overview",
            classification="public",
            source_urls=("https://owasp.org/www-project-top-ten/",),
            retrieved_at=date(2026, 11, 13),
            reuse_basis="Original summary of the public OWASP project page.",
        )
        self.content = (
            b"# OWASP Top 10 Overview\n\n"
            b"OWASP identifies recurring web application security risks for developers.\n"
        )

    def test_success_emits_staging_counts_then_searchable_after_commit(self):
        db = FakeSession()
        upload = FakeUpload("owasp.md", self.content)
        events = []

        def capture(event):
            if event["stage"] == "stage_vectors" or (
                event["stage"] == "promote" and event["status"] == "running"
            ):
                self.assertEqual(db.chunks, [])
            if event["stage"] == "searchable":
                self.assertTrue(db.chunks)
                self.assertTrue(event["terminal"])
            events.append(event)

        with patch(
            "services.ingestion.embedding_service.embed_batch",
            return_value=[[0.1] * 384],
        ):
            result = process_ingestion(
                db,
                upload,
                self.metadata,
                "admin-1",
                "job-1",
                capture,
            )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(len(db.chunks), 1)
        self.assertEqual(db.staging_chunks, [])
        self.assertEqual(db.documents[0].sync_state, "searchable")
        self.assertEqual(db.documents[0].origin, "admin_upload")
        self.assertEqual(db.chunks[0].allowed_roles, ["public", "internal", "restricted", "admin"])
        stage_events = [event for event in events if event["stage"] == "stage_vectors"]
        self.assertEqual(stage_events[-1]["vectors_written"], 1)
        self.assertTrue(events[-1]["terminal"])
        self.assertEqual(events[-1]["stage"], "searchable")
        promotion = next(event for event in events if event["stage"] == "promote" and event["status"] == "completed")
        self.assertEqual(promotion["committed_chunks"], len(db.chunks))
        self.assertGreaterEqual(db.commits, 4)

    def test_invalid_file_returns_failed_job_event_without_creating_documents(self):
        db = FakeSession()
        upload = FakeUpload("payload.exe", b"not a supported corpus file", "application/octet-stream")
        events = []

        result = process_ingestion(
            db,
            upload,
            self.metadata,
            "admin-1",
            "job-1",
            events.append,
        )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(db.documents, [])
        self.assertEqual(db.chunks, [])
        self.assertTrue(events[-1]["terminal"])
        self.assertEqual(events[-1]["error_code"], "UPLOAD_TYPE_INVALID")

    def test_upload_size_is_checked_before_document_parsing(self):
        db = FakeSession()
        events = []
        with patch("services.ingestion.settings.MAX_UPLOAD_SIZE_MB", 0):
            result = process_ingestion(
                db,
                FakeUpload("owasp.md", self.content),
                self.metadata,
                "admin-1",
                "job-1",
                events.append,
            )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(events[-1]["error_code"], "UPLOAD_SIZE_EXCEEDED")
        self.assertEqual(db.documents, [])

    def test_embedding_failure_cleans_staging_and_never_marks_searchable(self):
        db = FakeSession()
        events = []

        with patch(
            "services.ingestion.embedding_service.embed_batch",
            side_effect=EmbeddingServiceUnavailable("provider error"),
        ):
            result = process_ingestion(
                db,
                FakeUpload("owasp.md", self.content),
                self.metadata,
                "admin-1",
                "job-1",
                events.append,
            )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(db.staging_chunks, [])
        self.assertEqual(db.chunks, [])
        self.assertEqual(db.documents[0].sync_state, "failed")
        self.assertNotIn("searchable", [event["stage"] for event in events])
        self.assertEqual(events[-1]["error_code"], "EMBEDDING_UNAVAILABLE")

    def test_persistent_parser_failure_does_not_create_document_or_vectors(self):
        db = FakeSession()
        unsafe = b"# OWASP Top 10 Overview\n\n<script>alert(1)</script>\n"
        events = []

        result = process_ingestion(
            db,
            FakeUpload("owasp.md", unsafe),
            self.metadata,
            "admin-1",
            "job-1",
            events.append,
        )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(db.documents, [])
        self.assertEqual(db.staging_chunks, [])
        self.assertEqual(db.chunks, [])
        self.assertIn("G6_UNSAFE", {item["code"] for item in events[-1]["diagnostics"]})

    def test_promotion_commit_failure_rolls_back_production_chunks(self):
        db = FakeSession()
        db.fail_on_commit = 6
        events = []
        with patch(
            "services.ingestion.embedding_service.embed_batch",
            return_value=[[0.1] * 384],
        ):
            result = process_ingestion(
                db,
                FakeUpload("owasp.md", self.content),
                self.metadata,
                "admin-1",
                "job-1",
                events.append,
            )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(db.chunks, [])
        self.assertEqual(db.staging_chunks, [])
        self.assertEqual(db.documents[0].sync_state, "failed")
        self.assertNotIn("searchable", [event["stage"] for event in events])

    def test_embedding_and_staging_progress_are_batched_at_one_hundred(self):
        db = FakeSession()
        events = []
        many_lines = "# OWASP Top 10 Overview\n\n" + "\n".join(
            f"{'Risk category mitigation procedure ' * 20}{index}"
            for index in range(205)
        )

        def embed_batch(texts):
            return [[0.1] * 384 for _ in texts]

        with patch("services.ingestion.embedding_service.embed_batch", side_effect=embed_batch) as embed:
            result = process_ingestion(
                db,
                FakeUpload("owasp.md", many_lines.encode()),
                self.metadata,
                "admin-1",
                "job-1",
                events.append,
            )

        self.assertEqual(result["status"], "succeeded")
        self.assertTrue(all(len(call.args[0]) <= 100 for call in embed.call_args_list))
        self.assertGreaterEqual(len(embed.call_args_list), 2)
        vector_counts = [event["vectors_written"] for event in events if event["stage"] == "stage_vectors"]
        self.assertEqual(vector_counts, [0, 100, 200, 206])


if __name__ == "__main__":
    unittest.main()
