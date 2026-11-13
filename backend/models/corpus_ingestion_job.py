import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
)

from core.database import Base


class CorpusIngestionJob(Base):
    __tablename__ = "corpus_ingestion_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name="ck_corpus_jobs_status",
        ),
        CheckConstraint(
            "stage IN ('upload', 'parse', 'regex_validate', 'normalize', 'recheck', "
            "'chunk', 'embed', 'stage_vectors', 'promote', 'searchable')",
            name="ck_corpus_jobs_stage",
        ),
        Index("ix_corpus_jobs_admin", "admin_id", "created_at"),
        Index("ix_corpus_jobs_document", "document_id"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(
        String,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    admin_id = Column(String, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    status = Column(String, nullable=False, default="running")
    stage = Column(String, nullable=False, default="upload")
    sequence = Column(Integer, nullable=False, default=0)
    progress = Column(JSON, nullable=False, default=dict)
    diagnostics = Column(JSON, nullable=False, default=list)
    error_code = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
