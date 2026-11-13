"""Persistence helpers for safe, ordered corpus ingestion progress."""

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from core.database import SessionLocal
from models.corpus_ingestion_job import CorpusIngestionJob
from models.document import Document
from models.chunk import StagingChunk


_SAFE_CODE = re.compile(r"^[A-Z0-9_]{1,64}$")
_EVENT_FIELDS = (
    "message",
    "stage_status",
    "completed",
    "total",
    "timing_ms",
    "document_id",
    "vectors_written",
    "chunk_count",
    "searchable_at",
    "deduplicated",
)


def _safe_diagnostics(items: object) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    safe = []
    for item in items:
        if not isinstance(item, dict):
            continue
        code = item.get("code")
        severity = item.get("severity")
        message = item.get("message")
        line = item.get("line")
        if (
            not isinstance(code, str)
            or not _SAFE_CODE.fullmatch(code)
            or severity not in ("error", "warning")
            or not isinstance(message, str)
        ):
            continue
        safe.append({
            "code": code,
            "severity": severity,
            "message": message[:240],
            "line": line if isinstance(line, int) and line > 0 else None,
        })
    return safe


class CorpusJobStore:
    def touch(self, job_id: str) -> None:
        """Refresh the worker lease during long extraction/provider operations."""
        session = SessionLocal()
        try:
            job = session.query(CorpusIngestionJob).filter(
                CorpusIngestionJob.id == job_id,
                CorpusIngestionJob.status == "running",
            ).first()
            if job is not None:
                job.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                session.commit()
        finally:
            session.close()

    @staticmethod
    def recover_stale_jobs(
        db,
        now: datetime | None = None,
        stale_after: timedelta = timedelta(minutes=5),
        job_id: str | None = None,
        admin_id: str | None = None,
    ) -> int:
        """Reconcile jobs abandoned by a serverless worker or lost SSE request."""
        current_time = now or datetime.now(timezone.utc).replace(tzinfo=None)
        if current_time.tzinfo is not None:
            current_time = current_time.astimezone(timezone.utc).replace(tzinfo=None)
        cutoff = current_time - stale_after
        query = db.query(CorpusIngestionJob).filter(
            CorpusIngestionJob.status == "running",
            CorpusIngestionJob.updated_at < cutoff,
        )
        if job_id is not None:
            query = query.filter(CorpusIngestionJob.id == job_id)
        if admin_id is not None:
            query = query.filter(CorpusIngestionJob.admin_id == admin_id)
        jobs = query.with_for_update().all()
        recovered = 0
        for job in jobs:
            document = db.get(Document, job.document_id) if job.document_id else None
            db.query(StagingChunk).filter(StagingChunk.job_id == job.id).delete(synchronize_session=False)
            now_value = current_time
            job.updated_at = now_value
            job.finished_at = now_value
            job.sequence += 1
            progress = dict(job.progress or {})
            if document is not None and document.sync_state == "searchable":
                job.status = "succeeded"
                job.stage = "searchable"
                progress.update({
                    "stage_status": "completed",
                    "message": "Document is searchable; status recovered after worker interruption",
                    "document_id": document.id,
                    "chunk_count": document.chunk_count,
                    "vectors_written": document.vectors_written,
                    "searchable_at": document.searchable_at.isoformat() if document.searchable_at else None,
                })
            else:
                job.status = "failed"
                job.stage = "failed"
                job.error_code = "WORKER_INTERRUPTED"
                progress.update({
                    "stage_status": "failed",
                    "message": "Ingestion worker stopped before vectors became searchable; staged vectors were removed",
                    "error_code": job.error_code,
                })
                if document is not None:
                    document.sync_state = "failed"
                    document.updated_at = now_value
            job.progress = progress
            recovered += 1
        if recovered:
            db.commit()
        return recovered

    def create(self, admin_id: str, filename: str) -> dict:
        session = SessionLocal()
        try:
            safe_filename = (filename or "upload").replace("\\", "/").split("/")[-1][:255]
            job = CorpusIngestionJob(
                id=str(uuid.uuid4()),
                admin_id=admin_id,
                filename=safe_filename,
                status="running",
                stage="upload",
                sequence=0,
                progress={},
                diagnostics=[],
            )
            session.add(job)
            session.commit()
            session.refresh(job)
            return self._snapshot(job)
        finally:
            session.close()

    def record_progress(self, job_id: str, payload: dict) -> dict:
        session = SessionLocal()
        try:
            job = (
                session.query(CorpusIngestionJob)
                .filter(CorpusIngestionJob.id == job_id)
                .with_for_update()
                .first()
            )
            if job is None:
                raise LookupError("Corpus ingestion job not found")
            if job.status != "running":
                raise RuntimeError("Corpus ingestion job is already terminal")

            job.sequence += 1
            job.stage = payload.get("stage", job.stage)
            if isinstance(payload.get("document_id"), str):
                job.document_id = payload["document_id"]
            job.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            diagnostics = _safe_diagnostics(payload.get("diagnostics"))
            if diagnostics:
                job.diagnostics = diagnostics
            progress = dict(job.progress or {})
            if isinstance(payload.get("message"), str):
                progress["message"] = payload["message"][:240]
            progress["stage_status"] = payload.get("status", "running")
            for field in _EVENT_FIELDS:
                if field in payload:
                    progress[field] = payload[field]
            job.progress = progress

            terminal = payload.get("terminal") is True
            if terminal:
                job.status = "succeeded" if job.stage == "searchable" else "failed"
                job.finished_at = job.updated_at
                error_code = payload.get("error_code")
                job.error_code = (
                    error_code
                    if isinstance(error_code, str) and _SAFE_CODE.fullmatch(error_code)
                    else None
                )

            session.commit()
            event = {
                "job_id": job.id,
                "sequence": job.sequence,
                "stage": job.stage,
                "status": payload.get("status", "running"),
                "message": str(payload.get("message", ""))[:240],
                "diagnostics": diagnostics,
            }
            if job.error_code:
                event["error_code"] = job.error_code
            event.update({field: progress[field] for field in _EVENT_FIELDS if field in progress})
            if terminal:
                event["terminal"] = True
            return event
        finally:
            session.close()

    @staticmethod
    def _snapshot(job: CorpusIngestionJob) -> dict:
        return {
            "id": job.id,
            "document_id": job.document_id,
            "filename": job.filename,
            "status": job.status,
            "stage": job.stage,
            "sequence": job.sequence,
            "progress": job.progress or {},
            "diagnostics": _safe_diagnostics(job.diagnostics),
            "error_code": job.error_code,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "updated_at": job.updated_at,
        }
