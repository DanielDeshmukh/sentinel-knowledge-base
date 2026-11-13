import hashlib
import math
import re
from typing import List, Tuple

import httpx

from core.config import settings


EMBEDDING_VERSION = (
    f"{settings.NVIDIA_EMBEDDING_MODEL}:{settings.EMBEDDING_DIMENSION}:v1"
)


class EmbeddingServiceUnavailable(RuntimeError):
    pass


class EmbeddingService:
    MAX_BATCH_SIZE = 100

    def embed(self, text: str) -> List[float]:
        return self._embed_batch([text], "query")[0]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        for start in range(0, len(texts), self.MAX_BATCH_SIZE):
            embeddings.extend(
                self._embed_batch(texts[start:start + self.MAX_BATCH_SIZE], "passage")
            )
        return embeddings

    def _embed_batch(self, texts: List[str], input_type: str) -> List[List[float]]:
        if not texts:
            return []
        if not settings.NVIDIA_API_KEY:
            raise EmbeddingServiceUnavailable(
                "NVIDIA_API_KEY must be configured to use the embedding service."
            )

        try:
            response = httpx.post(
                settings.NVIDIA_EMBEDDING_API_URL,
                headers={
                    "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "input": texts,
                    "model": settings.NVIDIA_EMBEDDING_MODEL,
                    "input_type": input_type,
                    "dimensions": settings.EMBEDDING_DIMENSION,
                    "encoding_format": "float",
                    "truncate": "END",
                },
                timeout=60.0,
            )
            response.raise_for_status()
            response_data = response.json()["data"]
            ordered = sorted(response_data, key=lambda item: item["index"])
            embeddings = [
                [float(value) for value in item["embedding"]]
                for item in ordered
            ]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise EmbeddingServiceUnavailable(
                "NVIDIA embedding request failed or returned an invalid response."
            ) from error

        if len(embeddings) != len(texts) or any(
            len(vector) != settings.EMBEDDING_DIMENSION
            or not all(math.isfinite(value) for value in vector)
            for vector in embeddings
        ):
            raise EmbeddingServiceUnavailable(
                "NVIDIA embedding response did not match the configured vector dimension."
            )
        return embeddings

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        if len(vec1) != len(vec2):
            raise ValueError("Embedding vectors must have the same dimension")
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(value * value for value in vec1))
        magnitude2 = math.sqrt(sum(value * value for value in vec2))
        if not magnitude1 or not magnitude2:
            return 0.0
        return dot_product / (magnitude1 * magnitude2)


def compute_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[Tuple[str, str]]:
    lines = text.split("\n")
    chunks = []
    current_chunk = []
    current_heading = ""
    current_length = 0

    for line in lines:
        heading_match = re.match(r"^(#+)\s+(.+)", line)
        if heading_match:
            current_heading = heading_match.group(2)

        line_length = len(line)
        if current_length + line_length > chunk_size and current_chunk:
            chunk = "\n".join(current_chunk)
            chunks.append((chunk, current_heading))
            overlap_lines = current_chunk[-(overlap // 20):]
            current_chunk = overlap_lines
            current_length = sum(len(item) for item in current_chunk)
        else:
            current_chunk.append(line)
            current_length += line_length

    if current_chunk:
        chunks.append(("\n".join(current_chunk), current_heading))

    return chunks


embedding_service = EmbeddingService()
