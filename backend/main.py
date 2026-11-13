from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.database import engine, Base
from api.routes import router
from init_db import ensure_pgvector_extension, upgrade_embedding_schema, upgrade_user_schema

# Create tables
with engine.begin() as connection:
    ensure_pgvector_extension(connection)
Base.metadata.create_all(bind=engine)
with engine.begin() as connection:
    upgrade_user_schema(connection)
    upgrade_embedding_schema(connection)

app = FastAPI(
    title="Sentinel Knowledge Base",
    description="Permission-aware retrieval and chat system for cybersecurity and DPDP documents",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "sentinel-knowledge-base"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
