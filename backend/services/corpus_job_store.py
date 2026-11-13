"""Persistence helpers for safe, ordered corpus ingestion progress."""

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from core.database import SessionLocal
from models.corpus_ingestion_job import CorpusIngestionJob


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
