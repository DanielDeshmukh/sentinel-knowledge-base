import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from services.corpus_job_store import CorpusJobStore
from models.chunk import StagingChunk
from models.corpus_ingestion_job import CorpusIngestionJob


class RecoveryQuery:
    def __init__(self, items=None):
        self.items = items or []
        self.deleted = False

    def filter(self, *_criteria):
        return self

    def with_for_update(self):
        return self

    def all(self):
        return self.items

    def delete(self, **_kwargs):
        self.deleted = True
        return 1


class RecoverySession:
    def __init__(self, job, document):
        self.job = job
        self.document = document
        self.staging_query = RecoveryQuery()
        self.commits = 0

    def query(self, model):
        if model is CorpusIngestionJob:
            return RecoveryQuery([self.job])
        if model is StagingChunk:
            return self.staging_query
        raise AssertionError(f"Unexpected model: {model}")

    def get(self, _model, _identifier):
        return self.document

    def commit(self):
        self.commits += 1


class FakeQuery:
    def __init__(self, job):
        self.job = job

    def filter(self, *_args):
        return self

    def with_for_update(self):
        return self

    def first(self):
        return self.job


class FakeSession:
    def __init__(self, job):
        self.job = job
        self.commits = 0
        self.closed = False

    def query(self, _model):
        return FakeQuery(self.job)

    def add(self, job):
        self.job = job

    def refresh(self, _job):
        pass

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


class CorpusJobStoreTests(unittest.TestCase):
    def setUp(self):
        self.job = SimpleNamespace(
            id="job-1",
            status="running",
            stage="upload",
            sequence=0,
            progress={},
            diagnostics=[],
            error_code=None,
            updated_at=None,
            finished_at=None,
        )
        self.session = FakeSession(self.job)
        self.store = CorpusJobStore()

    def test_create_persists_job_with_safe_display_filename(self):
        with patch("services.corpus_job_store.SessionLocal", return_value=self.session):
            snapshot = self.store.create("admin-1", "..\\private\\owasp.md")

        self.assertEqual(snapshot["filename"], "owasp.md")
        self.assertEqual(snapshot["status"], "running")
        self.assertEqual(snapshot["sequence"], 0)
        self.assertEqual(self.session.commits, 1)
        self.assertTrue(self.session.closed)

    def test_record_progress_assigns_monotonic_sequence_and_persists_snapshot(self):
        with patch("services.corpus_job_store.SessionLocal", return_value=self.session):
            first = self.store.record_progress("job-1", {
                "stage": "embed", "status": "running", "message": "Embedding chunks",
                "completed": 10, "total": 20,
            })
            second = self.store.record_progress("job-1", {
                "stage": "stage_vectors", "status": "running", "message": "Writing vectors",
                "completed": 10, "total": 20,
            })

        self.assertEqual((first["sequence"], second["sequence"]), (1, 2))
        self.assertEqual(self.job.stage, "stage_vectors")
        self.assertEqual(self.job.progress["completed"], 10)
        self.assertEqual(self.job.progress["message"], "Writing vectors")
        self.assertEqual(self.job.progress["stage_status"], "running")
        self.assertEqual(self.session.commits, 2)
        self.assertTrue(self.session.closed)

    def test_record_progress_stores_only_safe_diagnostic_fields(self):
        with patch("services.corpus_job_store.SessionLocal", return_value=self.session):
            event = self.store.record_progress("job-1", {
                "stage": "regex_validate", "status": "failed", "message": "Sensitive match",
                "diagnostics": [{
                    "code": "G7_EMAIL", "severity": "error",
                    "message": "Email address detected", "line": 2,
                    "matched_value": "secret@example.test", "context": "private text",
                }],
            })

        self.assertEqual(event["diagnostics"], [{
            "code": "G7_EMAIL", "severity": "error",
            "message": "Email address detected", "line": 2,
        }])
        self.assertNotIn("matched_value", str(self.job.diagnostics))
        self.assertNotIn("context", str(self.job.diagnostics))

    def test_terminal_events_set_job_status_and_finish_time(self):
        with patch("services.corpus_job_store.SessionLocal", return_value=self.session):
            self.store.record_progress("job-1", {
                "stage": "searchable", "status": "completed", "message": "Ready",
                "terminal": True,
            })

        self.assertEqual(self.job.status, "succeeded")
        self.assertIsNotNone(self.job.finished_at)

    def test_touch_refreshes_running_job_lease_without_incrementing_sequence(self):
        self.job.sequence = 3
        with patch("services.corpus_job_store.SessionLocal", return_value=self.session):
            self.store.touch("job-1")

        self.assertIsNotNone(self.job.updated_at)
        self.assertEqual(self.job.sequence, 3)
        self.assertEqual(self.session.commits, 1)
        self.assertTrue(self.session.closed)

    def test_terminal_job_rejects_late_worker_progress(self):
        self.job.status = "failed"
        with patch("services.corpus_job_store.SessionLocal", return_value=self.session):
            with self.assertRaisesRegex(RuntimeError, "already terminal"):
                self.store.record_progress("job-1", {
                    "stage": "embed", "status": "running", "message": "late event",
                })

        self.assertEqual(self.job.sequence, 0)
        self.assertEqual(self.session.commits, 0)
        self.assertTrue(self.session.closed)

    def test_stale_worker_recovery_fails_document_and_removes_staging(self):
        now = datetime(2026, 11, 13, 12, 0)
        job = SimpleNamespace(
            id="job-stale", document_id="doc-1", status="running", stage="embed",
            sequence=4, progress={"completed": 1}, updated_at=now - timedelta(minutes=6),
            finished_at=None, error_code=None,
        )
        document = SimpleNamespace(id="doc-1", sync_state="staging", updated_at=None)
        db = RecoverySession(job, document)

        recovered = CorpusJobStore.recover_stale_jobs(db, now=now)

        self.assertEqual(recovered, 1)
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.stage, "failed")
        self.assertEqual(job.error_code, "WORKER_INTERRUPTED")
        self.assertEqual(job.sequence, 5)
        self.assertEqual(document.sync_state, "failed")
        self.assertTrue(db.staging_query.deleted)
        self.assertEqual(db.commits, 1)

    def test_stale_job_with_committed_searchable_document_recovers_as_success(self):
        now = datetime(2026, 11, 13, 12, 0)
        job = SimpleNamespace(
            id="job-stale", document_id="doc-1", status="running", stage="promote",
            sequence=4, progress={}, updated_at=now - timedelta(minutes=6),
            finished_at=None, error_code=None,
        )
        document = SimpleNamespace(
            id="doc-1", sync_state="searchable", chunk_count=3,
            vectors_written=3, searchable_at=now - timedelta(minutes=5), updated_at=None,
        )
        db = RecoverySession(job, document)

        recovered = CorpusJobStore.recover_stale_jobs(db, now=now)

        self.assertEqual(recovered, 1)
        self.assertEqual(job.status, "succeeded")
        self.assertEqual(job.stage, "searchable")
        self.assertEqual(job.progress["chunk_count"], 3)
        self.assertIsNone(job.error_code)


if __name__ == "__main__":
    unittest.main()
