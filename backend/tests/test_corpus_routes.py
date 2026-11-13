import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from starlette.datastructures import Headers
from starlette.datastructures import UploadFile

from api.routes import get_corpus_job_status, get_document, ingest, list_documents


class EmptyQuery:
    def __init__(self):
        self.criteria = []

    def filter(self, *_criteria):
        self.criteria.extend(_criteria)
        return self

    def first(self):
        return None

    def with_for_update(self):
        return self

    def all(self):
        return []


class FakeDb:
    def __init__(self):
        self.last_query = None

    def query(self, _model):
        self.last_query = EmptyQuery()
        return self.last_query

    def rollback(self):
        pass


class CorpusRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_ingest_streams_ordered_progress_and_passes_provenance(self):
        user = SimpleNamespace(id="admin-1", role="admin")
        db = FakeDb()
        upload = UploadFile(
            filename="owasp.md",
            file=io.BytesIO(b"# OWASP Top 10\n\nSummary"),
            headers=Headers({"content-type": "text/markdown"}),
        )
        recorded = []
        worker_uploads = []

        def record(_job_id, payload):
            recorded.append(payload)
            return {
                "job_id": "job-1",
                "sequence": len(recorded),
                **payload,
            }

        def fake_process(_db, worker_file, metadata, uploaded_by, job_id, callback):
            worker_uploads.append(worker_file)
            self.assertIsNot(worker_file, upload)
            self.assertEqual(worker_file.file.read(), b"# OWASP Top 10\n\nSummary")
            self.assertEqual(metadata.source_urls, ("https://owasp.org/top-ten/",))
            self.assertEqual(metadata.retrieved_at.isoformat(), "2026-11-13")
            self.assertEqual(uploaded_by, "admin-1")
            self.assertEqual(job_id, "job-1")
            callback({"stage": "upload", "status": "running", "message": "Reading"})
            callback({
                "stage": "searchable", "status": "completed", "message": "Ready",
                "terminal": True,
            })

        with (
            patch("api.routes.corpus_job_store.create", return_value={"id": "job-1"}),
            patch("api.routes.corpus_job_store.record_progress", side_effect=record),
            patch("api.routes.process_ingestion", side_effect=fake_process),
        ):
            response = await ingest(
                upload,
                "OWASP Top 10",
                "public",
                '["https://owasp.org/top-ten/"]',
                "2026-11-13",
                "Original public source summary",
                False,
                "",
                user,
            )
            body = "".join([
                part.decode() if isinstance(part, bytes) else part
                async for part in response.body_iterator
            ])

        self.assertIsInstance(response, StreamingResponse)
        self.assertTrue(response.media_type.startswith("text/event-stream"))
        self.assertEqual(response.headers["x-corpus-job-id"], "job-1")
        self.assertIn("id: 1\nevent: progress", body)
        self.assertIn('"stage":"searchable"', body)
        self.assertLess(body.index('"sequence":1'), body.index('"sequence":2'))
        self.assertTrue(worker_uploads[0].file.closed)

    async def test_ingestion_job_status_hides_jobs_owned_by_another_admin(self):
        db = FakeDb()
        with self.assertRaises(HTTPException) as raised:
            await get_corpus_job_status(
                "job-private",
                SimpleNamespace(id="admin-2", role="admin"),
                db,
            )

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail, "Ingestion job not found")
        self.assertEqual(len(db.last_query.criteria), 2)
        self.assertEqual(db.last_query.criteria[1].right.value, "admin-2")

    async def test_documents_list_includes_only_committed_searchable_records(self):
        db = FakeDb()

        await list_documents(SimpleNamespace(id="admin-1", role="admin"), db)

        self.assertTrue(any(
            "documents.sync_state" in str(criteria)
            and criteria.right.value == "searchable"
            for criteria in db.last_query.criteria
        ))

    async def test_document_detail_query_enforces_role_classification_and_searchable_state(self):
        db = FakeDb()
        with self.assertRaises(HTTPException) as raised:
            await get_document("secret-doc", SimpleNamespace(id="public-1", role="public"), db)

        self.assertEqual(raised.exception.status_code, 404)
        criteria = [str(item) for item in db.last_query.criteria]
        self.assertTrue(any("documents.sync_state" in item for item in criteria))
        self.assertTrue(any("documents.classification" in item for item in criteria))


if __name__ == "__main__":
    unittest.main()
