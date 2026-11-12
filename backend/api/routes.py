from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List
from core.database import get_db
from models.user import User
from models.document import Document
from models.chunk import Chunk, StagingChunk
from models.schemas import (
    UserCreate, UserLogin, Token, UserResponse,
    DocumentResponse, ChatRequest, ChatResponse, Citation,
    IngestionResponse, RoleUpdate
)
from services.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, require_admin
)
from services.ingestion import process_ingestion
from services.retrieval import handle_chat
from core.database import SessionLocal

router = APIRouter()


# ============ Auth Routes ============

@router.post("/auth/register", response_model=Token)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        display_name=user_data.display_name,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        role="public",
        approved=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(data={"sub": user.email})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/auth/login", response_model=Token)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.approved:
        raise HTTPException(status_code=403, detail="Account not approved")

    token = create_access_token(data={"sub": user.email})
    return {"access_token": token, "token_type": "bearer"}


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
        return db.query(Document).all()
    elif user.role == "restricted":
        return db.query(Document).filter(Document.classification.in_(["public", "internal", "restricted"])).all()
    elif user.role == "internal":
        return db.query(Document).filter(Document.classification.in_(["public", "internal"])).all()
    else:
        return db.query(Document).filter(Document.classification == "public").all()


@router.get("/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
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

@router.post("/ingest", response_model=IngestionResponse)
async def ingest(
    file: UploadFile = File(...),
    title: str = Form(...),
    classification: str = Form("restricted"),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    result = process_ingestion(db, file, title, classification, user.id)
    return result


# ============ Admin Routes ============

@router.get("/admin/users", response_model=List[UserResponse])
async def list_users(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(User).all()


@router.patch("/admin/users/{user_id}")
async def update_user_role(user_id: str, update: RoleUpdate, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.role = update.role
    db.commit()
    db.refresh(target)
    return target
