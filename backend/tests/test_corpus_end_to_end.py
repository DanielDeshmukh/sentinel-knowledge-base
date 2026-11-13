"""PostgreSQL/pgvector acceptance coverage; TEST_DATABASE_URL must be disposable."""

import asyncio
import io
import json
import os
import unittest
import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from starlette.datastructures import Headers, UploadFile

from corpus.parser import SYNTHETIC_LABEL, parse_corpus_record
from core.database import Base
from models.chunk import Chunk, StagingChunk
from models.corpus_ingestion_job import CorpusIngestionJob
from models.document import Document
from models.user import User
from services.corpus_job_store import CorpusJobStore
from services.embedding import EmbeddingServiceUnavailable
from services.ingestion import process_ingestion
from services.retrieval import handle_chat


def disposable_url():
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        return None
    url = make_url(value)
    if url.drivername == "postgresql+asyncpg":
        url = url.set(drivername="postgresql+psycopg2")
    return url


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "requires disposable PostgreSQL with pgvector")
class CorpusEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin_engine = create_engine(disposable_url())
        cls.schema = f"test_corpus_{uuid.uuid4().hex[:12]}"
        with cls.admin_engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            connection.execute(text(f'CREATE SCHEMA "{cls.schema}"'))
        cls.engine = create_engine(
            disposable_url(),
            connect_args={"options": f"-csearch_path={cls.schema},public"},
        )
        cls.session_factory = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        with cls.admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{cls.schema}" CASCADE'))
        cls.admin_engine.dispose()

    def setUp(self):
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.session_factory()
        self.admin = User(
            id="test-admin", display_name="Test Admin", email="test-admin@example.test",
            password_hash="not-used", role="admin", approved=True,
        )
        self.db.add(self.admin)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def add_role(self, role: str):
        user = User(
            id=f"test-{role}", display_name=f"Test {role}",
            email=f"test-{role}@example.test", password_hash="not-used",
            role=role, approved=True,
        )
        self.db.add(user)
        self.db.commit()
        return user

    def add_job(self, job_id: str):
        job = CorpusIngestionJob(
            id=job_id, admin_id=self.admin.id, filename="corpus.md", status="running",
            stage="upload", sequence=0, progress={}, diagnostics=[],
        )
        self.db.add(job)
        self.db.commit()
        return job

    @staticmethod
    def upload(filename: str, text_body: str):
        return UploadFile(
            filename=filename,
            file=io.BytesIO(text_body.encode("utf-8")),
            headers=Headers({"content-type": "text/markdown"}),
        )

    def progress_callback(self, job_id):
        return lambda payload: CorpusJobStore().record_progress(job_id, payload)

    def ingest_stream(self, *, classification, synthetic, text_body, title):
        from api.routes import ingest

        source_urls = [] if synthetic else ["https://owasp.org/www-project-top-ten/"]
        retrieved_at = "" if synthetic else "2026-11-13"
        reuse_basis = "Original concise summary for the Sentinel demonstration."
        upload = UploadFile(
            filename="corpus.md",
            file=io.BytesIO(text_body.encode("utf-8")),
            headers=Headers({"content-type": "text/markdown"}),
        )

        async def run():
            response = await ingest(
                upload,
                title,
                classification,
                json.dumps(source_urls),
                retrieved_at,
                reuse_basis,
                synthetic,
                SYNTHETIC_LABEL if synthetic else "",
                SimpleNamespace(id=self.admin.id, role="admin"),
            )
            events = []
            async for part in response.body_iterator:
                frame = part.decode() if isinstance(part, bytes) else part
                for line in frame.splitlines():
                    if line.startswith("data: "):
                        events.append(json.loads(line[6:]))
            return response, events

        with patch("services.corpus_job_store.SessionLocal", self.session_factory), patch(
            "api.routes.SessionLocal", self.session_factory
        ):
            return asyncio.run(run())

    def ask(self, role, question):
        user = SimpleNamespace(role=role)
        with (
            patch("services.retrieval.embedding_service.embed", return_value=[1.0] + [0.0] * 383),
            patch("services.retrieval.generate_answer", new=AsyncMock(return_value="grounded answer")),
        ):
            return asyncio.run(handle_chat(self.db, question, [], user))

    def test_public_original_corpus_streams_and_is_searchable_for_every_role(self):
        content = "# OWASP Top 10\n\nThe document summarizes common web application security risks and practical mitigations."
        with patch("services.ingestion.embedding_service.embed_batch", return_value=[[1.0] + [0.0] * 383]):
            response, events = self.ingest_stream(
                classification="public", synthetic=False, text_body=content, title="OWASP Top 10",
            )
        self.assertEqual(response.media_type, "text/event-stream")
        self.assertEqual(events[-1]["stage"], "searchable")
        self.assertTrue(events[-1]["terminal"])
        document_id = events[-1]["document_id"]
        self.db.expire_all()
        self.assertEqual(self.db.query(Chunk).filter(Chunk.document_id == document_id).count(), 1)
        self.assertEqual(self.db.query(StagingChunk).filter(StagingChunk.document_id == document_id).count(), 0)

        for role in ("public", "internal", "restricted", "admin"):
            result = self.ask(role, "What web application security risks are summarized?")
            self.assertEqual([item["document_id"] for item in result["citations"]], [document_id])

        from api.routes import get_document
        for role in ("public", "internal", "restricted", "admin"):
            document = asyncio.run(get_document(document_id, SimpleNamespace(role=role), self.db))
            self.assertEqual(document.id, document_id)

        duplicate_job_count = self.db.query(CorpusIngestionJob).count()
        with patch("services.ingestion.embedding_service.embed_batch") as embed:
            _, duplicate_events = self.ingest_stream(
                classification="public", synthetic=False, text_body=content, title="OWASP Top 10",
            )
        embed.assert_not_called()
        self.assertTrue(duplicate_events[-1]["deduplicated"])
        self.assertEqual(self.db.query(Document).count(), 1)
        self.assertEqual(self.db.query(Chunk).count(), 1)
        self.assertEqual(self.db.query(CorpusIngestionJob).count(), duplicate_job_count + 1)

    def test_restricted_synthetic_record_is_only_retrievable_by_restricted_and_admin(self):
        content = "# Synthetic Incident\n\nThis fictional incident describes a simulated account compromise and response steps."
        with patch("services.ingestion.embedding_service.embed_batch", return_value=[[1.0] + [0.0] * 383]):
            _, events = self.ingest_stream(
                classification="restricted", synthetic=True, text_body=content, title="Synthetic Incident",
            )
        document_id = events[-1]["document_id"]
        self.assertEqual(events[-1]["stage"], "searchable")
        for role in ("public", "internal"):
            result = self.ask(role, "What does the synthetic incident describe?")
            self.assertEqual(result["citations"], [])
            self.assertEqual(result["answer"], "I couldn't find anything relevant in your authorized documents.")
        for role in ("restricted", "admin"):
            result = self.ask(role, "What does the synthetic incident describe?")
            self.assertEqual([item["document_id"] for item in result["citations"]], [document_id])
        from api.routes import get_document
        for role in ("public", "internal"):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(get_document(document_id, SimpleNamespace(role=role), self.db))
            self.assertEqual(raised.exception.status_code, 404)
        for role in ("restricted", "admin"):
            self.assertEqual(asyncio.run(get_document(document_id, SimpleNamespace(role=role), self.db)).id, document_id)

    def test_parser_and_embedding_failures_leave_no_retrievable_content(self):
        unsafe = "# Unsafe Sample\n\n<script>alert(1)</script>"
        self.add_job("parser-failure")
        with patch("services.corpus_job_store.SessionLocal", self.session_factory):
            result = process_ingestion(
                self.db, self.upload("unsafe.md", unsafe), self.metadata("public"),
                self.admin.id, "parser-failure", self.progress_callback("parser-failure"),
            )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.db.query(Document).count(), 0)
        self.assertEqual(self.db.query(Chunk).count(), 0)

        self.add_job("embedding-failure")
        with patch("services.corpus_job_store.SessionLocal", self.session_factory), patch(
            "services.ingestion.embedding_service.embed_batch",
            side_effect=EmbeddingServiceUnavailable("provider unavailable"),
        ):
            result = process_ingestion(
                self.db, self.upload("valid.md", "# Valid\n\nValid summary."),
                self.metadata("public"), self.admin.id, "embedding-failure",
                self.progress_callback("embedding-failure"),
            )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.db.query(StagingChunk).count(), 0)
        self.assertEqual(self.db.query(Chunk).count(), 0)

    def test_retry_reuses_failed_record_and_removes_old_production_and_staging_chunks(self):
        content = "# OWASP Retry Sample\n\nThis original summary explains a security risk and practical mitigation."
        metadata = self.metadata("public")
        parsed = parse_corpus_record(content, metadata)
        failed = Document(
            id="failed-document", title=metadata.title, classification="public",
            uploaded_by=self.admin.id, content_sha256=parsed.content_sha256,
            sync_state="failed", chunk_count=1, vectors_written=0,
        )
        self.db.add(failed)
        self.db.add(Chunk(
            id="old-production-chunk", document_id=failed.id, text="old chunk",
            embedding=[1.0] + [0.0] * 383,
            allowed_roles=["public", "internal", "restricted", "admin"],
            content_hash="old-hash",
        ))
        self.db.add(StagingChunk(
            id="old-staging-chunk", document_id=failed.id, text="old staged chunk",
            embedding=[1.0] + [0.0] * 383,
            allowed_roles=["public", "internal", "restricted", "admin"],
            content_hash="old-stage-hash", job_id="old-job",
        ))
        self.db.commit()

        with patch("services.ingestion.embedding_service.embed_batch", return_value=[[1.0] + [0.0] * 383]):
            _, events = self.ingest_stream(
                classification="public", synthetic=False, text_body=content,
                title=metadata.title,
            )

        self.db.expire_all()
        self.assertEqual(events[-1]["stage"], "searchable")
        self.assertEqual(self.db.query(Document).count(), 1)
        self.assertEqual(self.db.query(Document).first().sync_state, "searchable")
        self.assertEqual(self.db.query(Chunk).filter(Chunk.document_id == failed.id).count(), 1)
        self.assertEqual(self.db.query(StagingChunk).filter(StagingChunk.document_id == failed.id).count(), 0)

    @staticmethod
    def metadata(classification):
        from corpus.parser import CorpusMetadata

        return CorpusMetadata(
            title="Public test record", classification=classification,
            source_urls=("https://owasp.org/www-project-top-ten/",),
            retrieved_at=date(2026, 11, 13), reuse_basis="Original summary for testing.",
        )


if __name__ == "__main__":
    unittest.main()
