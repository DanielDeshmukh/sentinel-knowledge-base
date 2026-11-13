import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.corpus_job_store import CorpusJobStore


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


if __name__ == "__main__":
    unittest.main()
