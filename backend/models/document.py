from sqlalchemy import (
    CheckConstraint,
    Column,
    String,
    DateTime,
    Date,
    ForeignKey,
    Integer,
    Boolean,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship
from core.database import Base
import uuid
from datetime import datetime


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "sync_state IN ('pending', 'validating', 'embedding', 'staging', "
            "'promoting', 'searchable', 'failed')",
            name="ck_documents_sync_state",
        ),
        CheckConstraint(
            "origin IN ('checked_in', 'admin_upload', 'legacy')",
            name="ck_documents_origin",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    classification = Column(String, nullable=False, default="restricted")
    source = Column(String, nullable=True)
    uploaded_by = Column(String, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    schema_version = Column(Integer, nullable=False, default=1)
    origin = Column(String, nullable=False, default="admin_upload")
    manifest_path = Column(String, nullable=True)
    markdown_content = Column(Text, nullable=True)
    content_sha256 = Column(String(64), nullable=True, index=True)
    content_bytes = Column(Integer, nullable=True)
    media_type = Column(String, nullable=True)
    source_urls = Column(JSON, nullable=False, default=list)
    retrieved_at = Column(Date, nullable=True)
    reuse_basis = Column(Text, nullable=True)
    synthetic = Column(Boolean, nullable=False, default=False)
    synthetic_label = Column(String, nullable=True)
    parser_version = Column(String, nullable=True)
    ruleset_version = Column(String, nullable=True)
    embedding_version = Column(String, nullable=True)
    embedding_dimension = Column(Integer, nullable=True)
    sync_state = Column(String, nullable=False, default="pending")
    chunk_count = Column(Integer, nullable=False, default=0)
    vectors_written = Column(Integer, nullable=False, default=0)
    searchable_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    uploaded_by_user = relationship("User", back_populates="documents")
