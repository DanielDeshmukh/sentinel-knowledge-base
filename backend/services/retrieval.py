import time
import httpx
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text
from fastapi import HTTPException
from models.user import User
from services.embedding import embedding_service
from core.config import settings


def retrieve_chunks(db: Session, question: str, user: User, top_k: int = None) -> List[dict]:
    top_k = top_k or settings.TOP_K
    question_embedding = embedding_service.embed(question)

    query = sql_text("""
        SELECT c.id, c.document_id, c.text, c.heading_path, c.content_hash,
               d.title as document_title,
               1 - (c.embedding <=> :embedding::vector) as similarity
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE :user_role = ANY(c.allowed_roles)
        ORDER BY c.embedding <=> :embedding::vector
        LIMIT :top_k
    """)

    result = db.execute(query, {
        "embedding": " [" + ",".join(map(str, question_embedding)) + "]",
        "user_role": user.role,
        "top_k": top_k
    })

    chunks = []
    for row in result.fetchall():
        similarity = float(row.similarity)
        if similarity >= settings.SIMILARITY_THRESHOLD:
            chunks.append({
                "chunk_id": row.id, "document_id": row.document_id,
                "document_title": row.document_title, "text": row.text,
                "heading_path": row.heading_path, "similarity": similarity
            })

    return chunks


async def generate_answer(question: str, conversation_history: List[dict], context_chunks: List[dict]) -> str:
    if not context_chunks:
        return "I couldn't find anything relevant in your authorized documents."

    context_parts = []
    for i, chunk in enumerate(context_chunks, 1):
        context_parts.append(f"[{i}] {chunk['text']}")
    context = "\n\n".join(context_parts)

    system_prompt = f"""You are a helpful assistant answering questions about cybersecurity and data protection documents.
Use the provided context to answer the question. Cite sources using the [N] markers.
If the context doesn't contain relevant information, say so clearly.

Context:
{context}"""

    messages = [{"role": "system", "content": system_prompt}]
    for msg in conversation_history[-6:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": question})

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.CHAT_API_URL,
                headers={"Authorization": f"Bearer {settings.CHAT_API_KEY}", "Content-Type": "application/json"},
                json={"model": settings.CHAT_MODEL, "messages": messages, "temperature": 0.3},
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    except Exception:
        return f"Based on the retrieved documents:\n\n{context}\n\n(Note: LLM API unavailable)"


async def handle_chat(db: Session, question: str, conversation_history: List[dict], user: User) -> dict:
    response_start = time.time()
    retrieval_start = time.time()
    chunks = retrieve_chunks(db, question, user)
    retrieval_time = (time.time() - retrieval_start) * 1000

    if chunks:
        answer = await generate_answer(question, conversation_history, chunks)
    else:
        answer = "I couldn't find anything relevant in your authorized documents."

    response_time = (time.time() - response_start) * 1000

    citations = []
    for chunk in chunks:
        citations.append({
            "chunk_id": chunk["chunk_id"], "document_id": chunk["document_id"],
            "document_title": chunk["document_title"],
            "text": chunk["text"][:500] + "..." if len(chunk["text"]) > 500 else chunk["text"],
            "heading_path": chunk["heading_path"]
        })

    return {
        "answer": answer, "citations": citations,
        "retrieval_time_ms": round(retrieval_time, 2),
        "response_time_ms": round(response_time, 2)
    }
