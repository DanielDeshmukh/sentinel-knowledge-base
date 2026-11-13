import os
from typing import Literal
from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/sentinel")

    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # NVIDIA's hosted free preview embedding endpoint; use the same model for both paths.
    EMBEDDING_DIMENSION: int = 384
    NVIDIA_EMBEDDING_API_URL: str = "https://integrate.api.nvidia.com/v1/embeddings"
    NVIDIA_EMBEDDING_MODEL: str = "nvidia/nemotron-3.5-embed-1b"

    # Free hosted chat providers; legacy CHAT_* environment variables are ignored.
    AI_PROVIDER: Literal["nvidia", "groq"] = "nvidia"
    NVIDIA_API_KEY: str = ""
    NVIDIA_CHAT_API_URL: str = "https://integrate.api.nvidia.com/v1/chat/completions"
    NVIDIA_CHAT_MODEL: str = "nvidia/nemotron-3.5-bolt-e4b"
    GROQ_API_KEY: str = ""
    GROQ_CHAT_API_URL: str = "https://api.groq.com/openai/v1/chat/completions"
    GROQ_CHAT_MODEL: str = ""

    # Search
    SIMILARITY_THRESHOLD: float = 0.45
    TOP_K: int = 5

    # Upload
    MAX_UPLOAD_SIZE_MB: int = 4

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @model_validator(mode="after")
    def require_groq_model(self):
        if self.AI_PROVIDER == "groq" and not self.GROQ_CHAT_MODEL.strip():
            raise ValueError("GROQ_CHAT_MODEL must be set when AI_PROVIDER=groq")
        return self

    @property
    def CHAT_API_KEY(self) -> str:
        return self.NVIDIA_API_KEY if self.AI_PROVIDER == "nvidia" else self.GROQ_API_KEY

    @property
    def CHAT_API_URL(self) -> str:
        return (
            self.NVIDIA_CHAT_API_URL
            if self.AI_PROVIDER == "nvidia"
            else self.GROQ_CHAT_API_URL
        )

    @property
    def CHAT_MODEL(self) -> str:
        return (
            self.NVIDIA_CHAT_MODEL
            if self.AI_PROVIDER == "nvidia"
            else self.GROQ_CHAT_MODEL
        )


settings = Settings()
