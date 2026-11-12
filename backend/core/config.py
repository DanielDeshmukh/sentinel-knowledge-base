import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/sentinel")

    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Embedding
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384

    # Chat
    CHAT_API_KEY: str = os.getenv("CHAT_API_KEY", "")
    CHAT_API_URL: str = os.getenv("CHAT_API_URL", "https://api.openai.com/v1/chat/completions")
    CHAT_MODEL: str = os.getenv("CHAT_MODEL", "gpt-4o-mini")

    # Search
    SIMILARITY_THRESHOLD: float = 0.75
    TOP_K: int = 5

    # Upload
    MAX_UPLOAD_SIZE_MB: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
