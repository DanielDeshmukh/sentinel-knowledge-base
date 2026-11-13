import io
import time
import uuid
from datetime import datetime, timezone
from typing import Callable, List, Dict
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from models.document import Document
from models.chunk import Chunk, StagingChunk
from services.auth import get_allowed_roles
from corpus.parser import CorpusMetadata, parse_corpus_record
from services.embedding import (
    EMBEDDING_VERSION,
    EmbeddingServiceUnavailable,
    chunk_text,
    compute_content_hash,
    embedding_service,
)
from core.config import settings


def extract_text_from_file(file: UploadFile, content: bytes) -> str:
    filename = file.filename or ""
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ""

    if ext == "md":
        return content.decode('utf-8')
    elif ext == "pdf":
        return extract_text_from_pdf(content)
    elif ext == "docx":
        return extract_text_from_docx(content)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type. Use md, pdf, or docx.")


def extract_text_from_pdf(content: bytes) -> str:
    from PyPDF2 import PdfReader
    reader = PdfReader(io.BytesIO(content))
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)
    return '\n\n'.join(text_parts)


def extract_text_from_docx(content: bytes) -> str:
    from docx import Document as DocxDocument
    doc = DocxDocument(io.BytesIO(content))
    text_parts = []
    for para in doc.paragraphs:
        if para.style.name.startswith('Heading'):
            level = int(para.style.name.replace('Heading', ''))
            text_parts.append(f"{'#' * level} {para.text}")
        else:
            text_parts.append(para.text)
    return '\n'.join(text_parts)


def process_ingestion(
    db: Session,
    file: UploadFile,
    metadata: CorpusMetadata,
    uploaded_by_id: str,
    job_id: str,
    on_progress: Callable[[dict], None],
) -> Dict:
    started_at = time.perf_counter()
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    stages: List[Dict] = []
    document: Document | None = None

    def emit(stage: str, status: str, message: str, **details) -> None:
        event = {
            "stage": stage,
            "status": status,
            "message": message,
            "timing_ms": details.pop("timing_ms", None),
        }
        event.update(details)
        stages.append({key: value for key, value in event.items() if value is not None})
        on_progress(event)

    def fail(code: str, message: str, diagnostics: list[dict] | None = None) -> Dict:
        db.rollback()
        if document is not None:
            try:
                db.query(StagingChunk).filter(StagingChunk.job_id == job_id).delete()
                document.sync_state = "failed"
                document.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                db.commit()
            except Exception:
                db.rollback()
        emit(
            stages[-1]["stage"] if stages else "upload",
            "failed",
            message,
            diagnostics=diagnostics or [],
            error_code=code,
            terminal=True,
            timing_ms=(time.perf_counter() - started_at) * 1000,
        )
        return {
            "document_id": document.id if document is not None else None,
            "stages": stages,
            "total_time_ms": (time.perf_counter() - started_at) * 1000,
            "status": "failed",
        }

    try:
        stage_start = time.perf_counter()
        emit("upload", "running", "Checking upload type and size")
        content = file.file.read(max_size + 1)
        file.file.seek(0)
        if len(content) > max_size:
            return fail("UPLOAD_SIZE_EXCEEDED", f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB limit")

        extension = (file.filename or "").rsplit(".", 1)[-1].lower()
        mime_type = (file.content_type or "").split(";", 1)[0].strip().lower()
        allowed_mime = {
            "md": {"text/markdown", "text/plain", "application/octet-stream"},
            "pdf": {"application/pdf"},
            "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        }
        if extension not in allowed_mime or mime_type not in allowed_mime[extension]:
            return fail("UPLOAD_TYPE_INVALID", "Use a Markdown, PDF, or DOCX file with a matching content type")
        emit(
            "upload", "completed", "Upload type and size are valid",
            timing_ms=(time.perf_counter() - stage_start) * 1000,
            completed=len(content), total=len(content),
        )

        stage_start = time.perf_counter()
        emit("parse", "running", "Extracting document text")
        try:
            text = extract_text_from_file(file, content)
        except (UnicodeDecodeError, ValueError, OSError):
            return fail("PARSE_FAILED", "The file could not be decoded or parsed")
        emit("parse", "completed", "Document text extracted", timing_ms=(time.perf_counter() - stage_start) * 1000)

        stage_start = time.perf_counter()
        emit("regex_validate", "running", "Running corpus validation rules")
        parsed = parse_corpus_record(text, metadata, normalize_on_failure=False)
        initial_diagnostics = [item.__dict__ for item in parsed.final_diagnostics]
        if parsed.valid:
            markdown = parsed.markdown
            final_diagnostics = []
            emit("regex_validate", "completed", "All corpus rules passed", timing_ms=(time.perf_counter() - stage_start) * 1000)
        else:
            emit(
                "regex_validate", "completed", "Some rules need normalization or correction",
                diagnostics=initial_diagnostics,
                timing_ms=(time.perf_counter() - stage_start) * 1000,
            )
            stage_start = time.perf_counter()
            emit("normalize", "running", "Normalizing document content")
            parsed = parse_corpus_record(text, metadata, normalize_on_failure=True)
            markdown = parsed.markdown
            emit(
                "normalize", "completed", "Normalization pass finished",
                diagnostics=[item.__dict__ for item in parsed.diagnostics],
                timing_ms=(time.perf_counter() - stage_start) * 1000,
            )
            stage_start = time.perf_counter()
            emit("recheck", "running", "Re-running all corpus rules")
            final_diagnostics = [item.__dict__ for item in parsed.final_diagnostics]
            if not parsed.valid:
                return fail(
                    "CORPUS_VALIDATION_FAILED",
                    "The document still fails corpus validation after normalization",
                    final_diagnostics,
                )
            emit("recheck", "completed", "All corpus rules passed after normalization", timing_ms=(time.perf_counter() - stage_start) * 1000)

        stage_start = time.perf_counter()
        emit("chunk", "running", "Creating document chunks")
        chunks = chunk_text(markdown)
        if not chunks:
            return fail("CORPUS_CONTENT_EMPTY", "No indexable text was found")
        document = Document(
            id=str(uuid.uuid4()),
            title=parsed.metadata.title,
            classification=parsed.metadata.classification,
            source=parsed.metadata.source_urls[0] if parsed.metadata.source_urls else None,
            uploaded_by=uploaded_by_id,
            origin="admin_upload",
            markdown_content=markdown,
            content_sha256=parsed.content_sha256,
            content_bytes=len(content),
            media_type=mime_type,
            source_urls=list(parsed.metadata.source_urls),
            retrieved_at=parsed.metadata.retrieved_at,
            reuse_basis=parsed.metadata.reuse_basis,
            synthetic=parsed.metadata.synthetic,
            synthetic_label=parsed.metadata.synthetic_label,
            parser_version=parsed.parser_version,
            ruleset_version=parsed.ruleset_version,
            embedding_version=EMBEDDING_VERSION,
            embedding_dimension=settings.EMBEDDING_DIMENSION,
            sync_state="validating",
            chunk_count=len(chunks),
            vectors_written=0,
        )
        db.add(document)
        db.commit()
        emit(
            "chunk", "completed", "Document chunks are ready",
            timing_ms=(time.perf_counter() - stage_start) * 1000,
            document_id=document.id, chunk_count=len(chunks), completed=len(chunks), total=len(chunks),
        )

        stage_start = time.perf_counter()
        emit("embed", "running", "Generating semantic embeddings", completed=0, total=len(chunks))
        chunk_vectors = []
        for start in range(0, len(chunks), 100):
            batch = chunks[start:start + 100]
            chunk_vectors.extend(embedding_service.embed_batch([chunk_text for chunk_text, _ in batch]))
            completed = min(start + len(batch), len(chunks))
            document.sync_state = "embedding"
            document.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
            emit(
                "embed", "running" if completed < len(chunks) else "completed",
                "Embedding document chunks",
                completed=completed, total=len(chunks), timing_ms=(time.perf_counter() - stage_start) * 1000,
            )

        stage_start = time.perf_counter()
        emit("stage_vectors", "running", "Writing vector batches to staging", completed=0, total=len(chunks), vectors_written=0)
        allowed_roles = get_allowed_roles(parsed.metadata.classification)
        for start in range(0, len(chunks), 100):
            for index in range(start, min(start + 100, len(chunks))):
                chunk_body, heading = chunks[index]
                db.add(StagingChunk(
                    id=str(uuid.uuid4()),
                    document_id=document.id,
                    text=chunk_body,
                    embedding=chunk_vectors[index],
                    allowed_roles=allowed_roles,
                    heading_path=heading,
                    content_hash=compute_content_hash(chunk_body),
                    embedding_version=EMBEDDING_VERSION,
                    job_id=job_id,
                ))
            db.flush()
            db.commit()
            written = min(start + 100, len(chunks))
            document.vectors_written = written
            document.sync_state = "staging"
            document.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
            emit(
                "stage_vectors", "running" if written < len(chunks) else "completed",
                "Writing vector batches to staging",
                completed=written, total=len(chunks), vectors_written=written,
                timing_ms=(time.perf_counter() - stage_start) * 1000,
            )

        stage_start = time.perf_counter()
        emit("promote", "running", "Promoting staged vectors")
        document.sync_state = "promoting"
        document.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        staging_chunks = db.query(StagingChunk).filter(StagingChunk.job_id == job_id).all()
        if len(staging_chunks) != len(chunks):
            raise RuntimeError("Staged vector count did not match the parsed chunk count")
        for staged in staging_chunks:
            db.add(Chunk(
                id=staged.id,
                document_id=staged.document_id,
                text=staged.text,
                embedding=staged.embedding,
                allowed_roles=staged.allowed_roles,
                heading_path=staged.heading_path,
                content_hash=staged.content_hash,
                embedding_version=staged.embedding_version,
            ))
        db.query(StagingChunk).filter(StagingChunk.job_id == job_id).delete(synchronize_session=False)
        document.sync_state = "searchable"
        document.vectors_written = len(chunks)
        document.searchable_at = datetime.now(timezone.utc).replace(tzinfo=None)
        document.updated_at = document.searchable_at
        db.commit()
        emit(
            "promote", "completed", "Vectors committed to the production index",
            timing_ms=(time.perf_counter() - stage_start) * 1000,
            committed_chunks=len(chunks),
        )

        total_time = (time.perf_counter() - started_at) * 1000
        emit(
            "searchable", "completed", "Document is searchable in role-authorized chat",
            document_id=document.id, chunk_count=len(chunks), vectors_written=len(chunks),
            completed=len(chunks), total=len(chunks),
            searchable_at=document.searchable_at.isoformat(), timing_ms=total_time,
            terminal=True,
        )
        return {
            "document_id": document.id,
            "stages": stages,
            "total_time_ms": total_time,
            "status": "succeeded",
        }
    except EmbeddingServiceUnavailable:
        return fail("EMBEDDING_UNAVAILABLE", "The embedding service is unavailable; no document was made searchable")
    except Exception:
        return fail("INGESTION_FAILED", "Ingestion failed; no document was made searchable")
