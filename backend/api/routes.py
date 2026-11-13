import asyncio
import io
import json
import queue
import threading
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
from core.database import get_db, SessionLocal
from core.config import settings
from models.user import User
from models.document import Document
from models.chunk import Chunk, StagingChunk
from models.schemas import (
    UserCreate, UserLogin, AuthToken, UserResponse,
    DocumentResponse, ChatRequest, ChatResponse, Citation,
    CorpusJobStatusResponse, RoleUpdate
)
from services.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, require_admin
)
from services.ingestion import process_ingestion
from services.corpus_job_store import CorpusJobStore
from models.corpus_ingestion_job import CorpusIngestionJob
from corpus.parser import CorpusMetadata
from services.retrieval import handle_chat

router = APIRouter()
corpus_job_store = CorpusJobStore()


# ============ Auth Routes ============

@router.post("/auth/register", response_model=AuthToken)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        display_name=user_data.display_name,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        role="public",
        approved=True,
        requested_role=user_data.requested_role,
        role_request_status="pending",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(data={"sub": user.email})
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.post("/auth/login", response_model=AuthToken)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.approved:
        raise HTTPException(status_code=403, detail="Account not approved")

    token = create_access_token(data={"sub": user.email})
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.get("/auth/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return user


# ============ Chat Routes ============

@router.post("/chat", response_model=ChatResponse)
async def chat(chat_request: ChatRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = await handle_chat(
        db=db, question=chat_request.question,
        conversation_history=[{"role": m.role, "content": m.content} for m in chat_request.conversation_history],
        user=user
    )
    return result


# ============ Document Routes ============

@router.get("/documents", response_model=List[DocumentResponse])
async def list_documents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role == "admin":
        return db.query(Document).filter(Document.sync_state == "searchable").all()
    elif user.role == "restricted":
        return db.query(Document).filter(
            Document.sync_state == "searchable",
            Document.classification.in_(["public", "internal", "restricted"]),
        ).all()
    elif user.role == "internal":
        return db.query(Document).filter(
            Document.sync_state == "searchable",
            Document.classification.in_(["public", "internal"]),
        ).all()
    else:
        return db.query(Document).filter(
            Document.sync_state == "searchable",
            Document.classification == "public",
        ).all()


@router.get("/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    visible_classifications = {
        "admin": ["public", "internal", "restricted"],
        "restricted": ["public", "internal", "restricted"],
        "internal": ["public", "internal"],
        "public": ["public"],
    }.get(user.role, ["public"])
    doc = db.query(Document).filter(
        Document.id == doc_id,
        Document.sync_state == "searchable",
        Document.classification.in_(visible_classifications),
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    db.query(Chunk).filter(Chunk.document_id == doc_id).delete()
    db.query(StagingChunk).filter(StagingChunk.document_id == doc_id).delete()
    db.delete(doc)
    db.commit()
    return {"message": "Document deleted"}


# ============ Ingestion Routes ============

@router.post("/ingest")
async def ingest(
    file: UploadFile = File(...),
    title: str = Form(...),
    classification: str = Form("restricted"),
    source_urls: str = Form("[]"),
    retrieved_at: str = Form(""),
    reuse_basis: str = Form(""),
    synthetic: bool = Form(False),
    synthetic_label: str = Form(""),
    user: User = Depends(require_admin),
):
    try:
        parsed_sources = json.loads(source_urls or "[]")
    except json.JSONDecodeError:
        parsed_sources = []
    if not isinstance(parsed_sources, list) or any(not isinstance(url, str) for url in parsed_sources):
        parsed_sources = []
    try:
        retrieved_date = date.fromisoformat(retrieved_at) if retrieved_at else None
    except ValueError:
        retrieved_date = None

    upload_bytes = await file.read(settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024 + 1)
    worker_file = UploadFile(
        filename=file.filename,
        file=io.BytesIO(upload_bytes),
        headers=file.headers,
    )

    metadata = CorpusMetadata(
        title=title,
        classification=classification,
        source_urls=tuple(parsed_sources),
        retrieved_at=retrieved_date,
        reuse_basis=reuse_basis,
        synthetic=synthetic,
        synthetic_label=synthetic_label or None,
    )
    job = corpus_job_store.create(user.id, file.filename or "upload")
    event_queue: queue.Queue = queue.Queue()
    heartbeat_stop = threading.Event()

    def keep_worker_lease() -> None:
        while not heartbeat_stop.wait(30):
            try:
                corpus_job_store.touch(job["id"])
            except Exception:
                # The next successful progress event refreshes the same lease.
                continue

    def publish_progress(payload: dict) -> None:
        event_queue.put(corpus_job_store.record_progress(job["id"], payload))

    def run_worker() -> None:
        worker_db = SessionLocal()
        try:
            process_ingestion(
                worker_db,
                worker_file,
                metadata,
                user.id,
                job["id"],
                publish_progress,
            )
        except Exception:
            worker_db.rollback()
            try:
                publish_progress({
                    "stage": "failed",
                    "status": "failed",
                    "message": "Ingestion failed; no document was made searchable",
                    "error_code": "INGESTION_FAILED",
                    "terminal": True,
                })
            except Exception:
                pass
        finally:
            worker_db.close()
            worker_file.file.close()
            heartbeat_stop.set()
            event_queue.put(None)

    async def event_stream():
        heartbeat = threading.Thread(target=keep_worker_lease, name=f"corpus-heartbeat-{job['id']}", daemon=True)
        worker = threading.Thread(target=run_worker, name=f"corpus-ingest-{job['id']}", daemon=True)
        heartbeat.start()
        worker.start()
        try:
            while True:
                try:
                    event = await asyncio.to_thread(event_queue.get, True, 15)
                except queue.Empty:
                    yield ": keep-alive\n\n"
                    continue
                if event is None:
                    break
                event_id = event.get("sequence", "")
                yield f"id: {event_id}\nevent: progress\ndata: {json.dumps(event, separators=(',', ':'))}\n\n"
        finally:
            # The job continues independently of the SSE client. Its lease and
            # DB/upload resources stay alive until the worker finishes.
            worker.join(timeout=1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "X-Corpus-Job-ID": job["id"],
        },
    )


@router.get("/admin/corpus/jobs/{job_id}", response_model=CorpusJobStatusResponse)
async def get_corpus_job_status(
    job_id: str,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    corpus_job_store.recover_stale_jobs(db, job_id=job_id, admin_id=user.id)
    job = db.query(CorpusIngestionJob).filter(
        CorpusIngestionJob.id == job_id,
        CorpusIngestionJob.admin_id == user.id,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    return job


# ============ Admin Routes ============

@router.get("/admin/users", response_model=List[UserResponse])
async def list_users(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(User).all()


@router.get("/admin/access/requests", response_model=List[UserResponse])
async def list_access_requests(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(User).filter(User.role_request_status == "pending").order_by(User.created_at.desc()).all()


@router.patch("/admin/access/requests/{user_id}", response_model=UserResponse)
async def review_access_request(user_id: str, update: RoleUpdate, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if update.role == "admin":
        raise HTTPException(status_code=422, detail="Access requests can only be assigned public, internal, or restricted roles")
    target = db.query(User).filter(User.id == user_id, User.role_request_status == "pending").first()
    if not target:
        raise HTTPException(status_code=404, detail="Pending access request not found")
    target.role = update.role
    target.role_request_status = "reviewed"
    db.commit()
    db.refresh(target)
    return target


@router.patch("/admin/users/{user_id}")
async def update_user_role(user_id: str, update: RoleUpdate, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.role = update.role
    if target.role_request_status == "pending":
        target.role_request_status = "reviewed"
    db.commit()
    db.refresh(target)
    return target
