import io
import time
import uuid
from typing import List, Dict, Optional
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from models.document import Document
from models.chunk import Chunk, StagingChunk
from services.auth import get_allowed_roles
from services.gates import run_gates, normalize_text
from services.embedding import chunk_text, compute_content_hash, embedding_service
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
    title: str,
    classification: str,
    uploaded_by_id: str
) -> Dict:
    start_time = time.time()
    stages: List[Dict] = []

    # Stage 1: Upload
    stage_start = time.time()
    stages.append({"stage": "upload", "status": "running", "message": "Reading file..."})

    content = file.file.read()
    file.file.seek(0)

    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_size:
        stages[-1]["status"] = "failed"
        stages[-1]["message"] = f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit"
        stages[-1]["timing_ms"] = (time.time() - stage_start) * 1000
        return {"document_id": None, "stages": stages, "total_time_ms": (time.time() - start_time) * 1000, "status": "failed"}

    stages[-1]["status"] = "completed"
    stages[-1]["timing_ms"] = (time.time() - stage_start) * 1000

    # Stage 2: Gate check
    stage_start = time.time()
    stages.append({"stage": "gate_check", "status": "running", "message": "Running regex gates..."})

    try:
        text = extract_text_from_file(file, content)
    except HTTPException as e:
        stages[-1]["status"] = "failed"
        stages[-1]["message"] = str(e.detail)
        stages[-1]["timing_ms"] = (time.time() - stage_start) * 1000
        return {"document_id": None, "stages": stages, "total_time_ms": (time.time() - start_time) * 1000, "status": "failed"}

    metadata = {"title": title, "classification": classification}
    passed, failures = run_gates(text, metadata)

    if passed:
        stages[-1]["status"] = "completed"
        stages[-1]["message"] = "All gates passed"
    else:
        stages[-1]["status"] = "completed"
        stages[-1]["message"] = f"Gates failed: {', '.join(f['name'] for f in failures)}. Normalizing..."

    stages[-1]["timing_ms"] = (time.time() - stage_start) * 1000

    # Stage 3: Normalize (if gates failed)
    if not passed:
        stage_start = time.time()
        stages.append({"stage": "normalize", "status": "running", "message": "Normalizing content..."})
        text = normalize_text(text, metadata)
        stages[-1]["status"] = "completed"
        stages[-1]["message"] = "Normalization complete"
        stages[-1]["timing_ms"] = (time.time() - stage_start) * 1000

        # Stage 4: Re-check gates
        stage_start = time.time()
        stages.append({"stage": "recheck", "status": "running", "message": "Re-running gates..."})
        passed, failures = run_gates(text, metadata)
        if not passed:
            stages[-1]["status"] = "failed"
            stages[-1]["message"] = f"Still failing after normalization: {', '.join(f['message'] for f in failures)}"
            stages[-1]["timing_ms"] = (time.time() - stage_start) * 1000
            return {"document_id": None, "stages": stages, "total_time_ms": (time.time() - start_time) * 1000, "status": "failed"}

        stages[-1]["status"] = "completed"
        stages[-1]["message"] = "Re-check passed"
        stages[-1]["timing_ms"] = (time.time() - stage_start) * 1000

    # Stage 5: Chunk
    stage_start = time.time()
    stages.append({"stage": "chunk", "status": "running", "message": "Splitting into chunks..."})

    chunks = chunk_text(text)
    doc_id = str(uuid.uuid4())
    document = Document(id=doc_id, title=title, classification=classification, uploaded_by=uploaded_by_id)
    db.add(document)
    db.flush()

    stages[-1]["status"] = "completed"
    stages[-1]["message"] = f"Created {len(chunks)} chunks"
    stages[-1]["timing_ms"] = (time.time() - stage_start) * 1000

    # Stage 6: Embed
    stage_start = time.time()
    stages.append({"stage": "embed", "status": "running", "message": "Generating embeddings..."})
    chunk_texts = [c[0] for c in chunks]
    embeddings = embedding_service.embed_batch(chunk_texts)
    stages[-1]["status"] = "completed"
    stages[-1]["message"] = "Embeddings generated"
    stages[-1]["timing_ms"] = (time.time() - stage_start) * 1000

    # Stage 7: Stage
    stage_start = time.time()
    stages.append({"stage": "stage", "status": "running", "message": "Writing to staging..."})
    allowed_roles = get_allowed_roles(classification)

    for i, (chunk_txt, heading) in enumerate(chunks):
        staging_chunk = StagingChunk(
            id=str(uuid.uuid4()), document_id=doc_id, text=chunk_txt,
            embedding=embeddings[i], allowed_roles=allowed_roles,
            heading_path=heading, content_hash=compute_content_hash(chunk_txt)
        )
        db.add(staging_chunk)
    db.flush()

    stages[-1]["status"] = "completed"
    stages[-1]["message"] = f"Staged {len(chunks)} chunks"
    stages[-1]["timing_ms"] = (time.time() - stage_start) * 1000

    # Stage 8: Promote
    stage_start = time.time()
    stages.append({"stage": "promote", "status": "running", "message": "Promoting to production..."})
    staging_chunks = db.query(StagingChunk).filter(StagingChunk.document_id == doc_id).all()

    for sc in staging_chunks:
        chunk = Chunk(
            id=sc.id, document_id=sc.document_id, text=sc.text,
            embedding=sc.embedding, allowed_roles=sc.allowed_roles,
            heading_path=sc.heading_path, content_hash=sc.content_hash
        )
        db.add(chunk)

    db.query(StagingChunk).filter(StagingChunk.document_id == doc_id).delete()
    db.commit()

    stages[-1]["status"] = "completed"
    stages[-1]["message"] = "Promoted to production"
    stages[-1]["timing_ms"] = (time.time() - stage_start) * 1000

    # Stage 9: Searchable
    total_time = (time.time() - start_time) * 1000
    stages.append({"stage": "searchable", "status": "completed", "message": "Document is now searchable", "timing_ms": 0})

    return {"document_id": doc_id, "stages": stages, "total_time_ms": total_time, "status": "completed"}
