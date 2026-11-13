from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from core.database import Base
from core.config import settings
import uuid


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(Vector(settings.EMBEDDING_DIMENSION), nullable=False)
    allowed_roles = Column(ARRAY(String), nullable=False)
    heading_path = Column(String, nullable=True)
    content_hash = Column(String, nullable=False)
    embedding_version = Column(String, nullable=True)

    document = relationship("Document", back_populates="chunks")


class StagingChunk(Base):
    __tablename__ = "staging_chunks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(Vector(settings.EMBEDDING_DIMENSION), nullable=False)
    allowed_roles = Column(ARRAY(String), nullable=False)
    heading_path = Column(String, nullable=True)
    content_hash = Column(String, nullable=False)
    embedding_version = Column(String, nullable=True)
    job_id = Column(String, nullable=True, index=True)
