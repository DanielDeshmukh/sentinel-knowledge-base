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
from sqlalchemy import text
from sqlalchemy.engine import Connection


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


def init_db():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("[OK] Tables created")

    with engine.begin() as connection:
        upgrade_user_schema(connection)

    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    print("[OK] pgvector extension enabled")

    print("\nDatabase initialization complete!")


if __name__ == "__main__":
    init_db()
