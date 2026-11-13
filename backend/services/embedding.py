import hashlib
import logging
import math
import re
import time
from typing import List, Tuple

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_VERSION = (
    f"{settings.NVIDIA_EMBEDDING_MODEL}:{settings.EMBEDDING_DIMENSION}:v1"
)


class EmbeddingServiceUnavailable(RuntimeError):
    pass


class EmbeddingService:
    # Keep provider requests small: transient NIM failures have been observed
    # on multi-chunk ingestion requests, and smaller batches limit their scope.
    MAX_BATCH_SIZE = 5
    MAX_RETRIES = 2

    def embed(self, text: str) -> List[float]:
        return self._embed_batch([text], "query")[0]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        for start in range(0, len(texts), self.MAX_BATCH_SIZE):
            embeddings.extend(
                self._embed_batch(
                    texts[start:start + self.MAX_BATCH_SIZE], "passage", start
                )
            )
        return embeddings

    def _embed_batch(
        self, texts: List[str], input_type: str, batch_offset: int = 0
    ) -> List[List[float]]:
        if not texts:
            return []
        if not settings.NVIDIA_API_KEY:
            raise EmbeddingServiceUnavailable(
                "NVIDIA_API_KEY must be configured to use the embedding service."
            )

        response = None
        for attempt in range(self.MAX_RETRIES + 1):
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
                break
            except httpx.HTTPStatusError as error:
                response = error.response
                request_id = (
                    response.headers.get("request-id")
                    or response.headers.get("x-request-id")
                    or response.headers.get("nvcf-reqid")
                    or "unavailable"
                )
                logger.warning(
                    "NVIDIA embedding provider returned HTTP %s (request_id=%s, "
                    "batch_size=%s, input_type=%s, item_range=%s-%s, attempt=%s/%s).",
                    response.status_code,
                    request_id,
                    len(texts),
                    input_type,
                    batch_offset + 1,
                    batch_offset + len(texts),
                    attempt + 1,
                    self.MAX_RETRIES + 1,
                )
                retryable = response.status_code == 429 or response.status_code >= 500
                if not retryable or attempt == self.MAX_RETRIES:
                    if response.status_code == 500 and len(texts) > 1:
                        midpoint = len(texts) // 2
                        logger.warning(
                            "Splitting NVIDIA embedding batch after repeated HTTP 500 "
                            "(item_range=%s-%s).",
                            batch_offset + 1,
                            batch_offset + len(texts),
                        )
                        return self._embed_batch(
                            texts[:midpoint], input_type, batch_offset
                        ) + self._embed_batch(
                            texts[midpoint:], input_type, batch_offset + midpoint
                        )
                    raise EmbeddingServiceUnavailable(
                        f"NVIDIA embedding provider returned HTTP {response.status_code}. "
                        f"Request ID: {request_id}. Failed item position: "
                        f"{batch_offset + 1}."
                    ) from error
            except httpx.RequestError as error:
                logger.warning(
                    "NVIDIA embedding transport error (batch_size=%s, attempt=%s/%s, "
                    "error_type=%s).",
                    len(texts),
                    attempt + 1,
                    self.MAX_RETRIES + 1,
                    type(error).__name__,
                )
                if attempt == self.MAX_RETRIES:
                    raise EmbeddingServiceUnavailable(
                        "NVIDIA embedding provider could not be reached after retries."
                    ) from error
            except (KeyError, TypeError, ValueError) as error:
                logger.exception("NVIDIA embedding provider returned an invalid response.")
                raise EmbeddingServiceUnavailable(
                    "NVIDIA embedding request returned an invalid response."
                ) from error

            time.sleep(0.5 * (2 ** attempt))

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
