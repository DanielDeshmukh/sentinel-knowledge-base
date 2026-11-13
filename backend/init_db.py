"""
Database initialization script for Sentinel Knowledge Base.
Run this to set up the PostgreSQL database with pgvector extension.

Usage:
    python init_db.py
"""
from core.database import engine, Base
from models.user import User
from models.document import Document
from models.chunk import Chunk, StagingChunk
from models.corpus_ingestion_job import CorpusIngestionJob
from sqlalchemy import text
from sqlalchemy.engine import Connection
from core.config import settings
from services.embedding import EMBEDDING_VERSION, embedding_service


def ensure_pgvector_extension(connection: Connection) -> None:
    connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def upgrade_user_schema(connection: Connection) -> None:
    connection.execute(text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR"
    ))
    connection.execute(text("""
        UPDATE users
        SET display_name = INITCAP(
            REGEXP_REPLACE(SPLIT_PART(email, '@', 1), '[._-]+', ' ', 'g')
        )
        WHERE display_name IS NULL OR BTRIM(display_name) = ''
    """))
    connection.execute(text(
        "ALTER TABLE users ALTER COLUMN display_name SET NOT NULL"
    ))


def upgrade_corpus_schema(connection: Connection) -> None:
    """Add corpus record and persisted ingestion progress fields without destructive changes."""
    connection.execute(text("SELECT pg_advisory_xact_lock(20261113, 2)"))

    document_columns = (
        ("schema_version", "INTEGER NOT NULL DEFAULT 1"),
        ("origin", "VARCHAR NOT NULL DEFAULT 'admin_upload'"),
        ("manifest_path", "VARCHAR"),
        ("markdown_content", "TEXT"),
        ("content_sha256", "VARCHAR(64)"),
        ("content_bytes", "INTEGER"),
        ("media_type", "VARCHAR"),
        ("source_urls", "JSON NOT NULL DEFAULT '[]'::json"),
        ("retrieved_at", "DATE"),
        ("reuse_basis", "TEXT"),
        ("synthetic", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("synthetic_label", "VARCHAR"),
        ("parser_version", "VARCHAR"),
        ("ruleset_version", "VARCHAR"),
        ("embedding_version", "VARCHAR"),
        ("embedding_dimension", "INTEGER"),
        ("sync_state", "VARCHAR NOT NULL DEFAULT 'searchable'"),
        ("chunk_count", "INTEGER NOT NULL DEFAULT 0"),
        ("vectors_written", "INTEGER NOT NULL DEFAULT 0"),
        ("searchable_at", "TIMESTAMP"),
        ("updated_at", "TIMESTAMP NOT NULL DEFAULT NOW()"),
    )
    for column_name, column_type in document_columns:
        connection.execute(text(
            f"ALTER TABLE documents ADD COLUMN IF NOT EXISTS {column_name} {column_type}"
        ))
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_documents_content_sha256 "
        "ON documents (content_sha256)"
    ))
    connection.execute(text("""
        DO $$ BEGIN
            ALTER TABLE documents ADD CONSTRAINT ck_documents_sync_state CHECK (
                sync_state IN ('pending', 'validating', 'embedding', 'staging',
                               'promoting', 'searchable', 'failed')
            ) NOT VALID;
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))
    connection.execute(text("""
        DO $$ BEGIN
            ALTER TABLE documents ADD CONSTRAINT ck_documents_origin CHECK (
                origin IN ('checked_in', 'admin_upload', 'legacy')
            ) NOT VALID;
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))

    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS corpus_ingestion_jobs (
            id VARCHAR PRIMARY KEY,
            document_id VARCHAR REFERENCES documents(id) ON DELETE SET NULL,
            admin_id VARCHAR NOT NULL REFERENCES users(id),
            filename VARCHAR NOT NULL,
            status VARCHAR NOT NULL DEFAULT 'running'
                CHECK (status IN ('running', 'succeeded', 'failed')),
            stage VARCHAR NOT NULL DEFAULT 'upload',
            sequence INTEGER NOT NULL DEFAULT 0,
            progress JSON NOT NULL DEFAULT '{}'::json,
            diagnostics JSON NOT NULL DEFAULT '[]'::json,
            error_code VARCHAR,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            started_at TIMESTAMP NOT NULL DEFAULT NOW(),
            finished_at TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_corpus_jobs_admin "
        "ON corpus_ingestion_jobs (admin_id, created_at)"
    ))
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_corpus_jobs_document "
        "ON corpus_ingestion_jobs (document_id)"
    ))

    connection.execute(text(
        "ALTER TABLE staging_chunks ADD COLUMN IF NOT EXISTS job_id VARCHAR"
    ))
    connection.execute(text(
        "ALTER TABLE staging_chunks ADD COLUMN IF NOT EXISTS embedding_version VARCHAR"
    ))
    connection.execute(text(
        "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS embedding_version VARCHAR"
    ))
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_staging_chunks_job_id ON staging_chunks (job_id)"
    ))


def upgrade_embedding_schema(connection: Connection) -> None:
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS sentinel_schema_migrations (
            version VARCHAR PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    connection.execute(text("SELECT pg_advisory_xact_lock(20261113, 1)"))

    already_applied = connection.execute(
        text("SELECT 1 FROM sentinel_schema_migrations WHERE version = :version"),
        {"version": EMBEDDING_VERSION},
    ).first()
    if already_applied:
        return
    if not settings.NVIDIA_API_KEY:
        raise RuntimeError(
            "NVIDIA_API_KEY is required to migrate existing document embeddings."
        )

    for table_name in ("chunks", "staging_chunks"):
        column_type = connection.execute(text("""
            SELECT udt_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = :table_name
              AND column_name = 'embedding'
        """), {"table_name": table_name}).first()
        if not column_type:
            continue
        if column_type[0] in ("_int4", "_float8"):
            connection.execute(text(f"""
                ALTER TABLE {table_name}
                ALTER COLUMN embedding TYPE vector({settings.EMBEDDING_DIMENSION})
                USING ('[' || array_to_string(embedding, ',') || ']')::vector({settings.EMBEDDING_DIMENSION})
            """))
        elif column_type[0] != "vector":
            raise RuntimeError(
                f"Unsupported embedding column type for {table_name}: {column_type[0]}"
            )

        last_id = ""
        batch_size = 100
        while True:
            rows = connection.execute(text(f"""
                SELECT id, text FROM {table_name}
                WHERE id > :last_id
                ORDER BY id
                LIMIT :batch_size
            """), {"last_id": last_id, "batch_size": batch_size}).fetchall()
            if not rows:
                break

            embeddings = embedding_service.embed_batch([row.text for row in rows])
            for row, embedding in zip(rows, embeddings):
                vector_value = "[" + ",".join(map(str, embedding)) + "]"
                connection.execute(text(f"""
                    UPDATE {table_name}
                    SET embedding = CAST(:embedding AS vector({settings.EMBEDDING_DIMENSION}))
                    WHERE id = :id
                """), {"id": row.id, "embedding": vector_value})
            last_id = rows[-1].id

    connection.execute(
        text("INSERT INTO sentinel_schema_migrations (version) VALUES (:version)"),
        {"version": EMBEDDING_VERSION},
    )


def init_db():
    print("Creating database tables...")
    with engine.begin() as connection:
        ensure_pgvector_extension(connection)
    Base.metadata.create_all(bind=engine)
    print("[OK] Tables created")

    with engine.begin() as connection:
        upgrade_user_schema(connection)
        upgrade_corpus_schema(connection)
        upgrade_embedding_schema(connection)
    print("[OK] pgvector extension enabled")

    print("\nDatabase initialization complete!")


if __name__ == "__main__":
    init_db()
