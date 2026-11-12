from pydantic import BaseModel, field_validator
from typing import List, Optional
from datetime import datetime


# Auth
class UserCreate(BaseModel):
    display_name: str
    email: str
    password: str

    @field_validator("display_name")
    @classmethod
    def display_name_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Display name cannot be blank")
        return normalized


class UserLogin(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class UserResponse(BaseModel):
    id: str
    display_name: str
    email: str
    role: str
    approved: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Documents
class DocumentCreate(BaseModel):
    title: str
    classification: str
    source: Optional[str] = None


class DocumentResponse(BaseModel):
    id: str
    title: str
    classification: str
    source: Optional[str]
    uploaded_by: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# Chunks
class ChunkResponse(BaseModel):
    id: str
    document_id: str
    text: str
    heading_path: Optional[str]
    content_hash: str

    class Config:
        from_attributes = True


# Chat
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    conversation_history: List[ChatMessage] = []


class Citation(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    text: str
    heading_path: Optional[str]


class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation]
    retrieval_time_ms: float
    response_time_ms: float


# Ingestion
class IngestionStage(BaseModel):
    stage: str
    status: str
    timing_ms: Optional[float] = None
    message: Optional[str] = None


class IngestionResponse(BaseModel):
    document_id: str
    stages: List[IngestionStage]
    total_time_ms: float
    status: str


# Admin
class RoleUpdate(BaseModel):
    role: str
