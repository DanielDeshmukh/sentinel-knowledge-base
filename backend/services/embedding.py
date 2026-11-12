import hashlib
import re
from typing import List, Tuple
from sentence_transformers import SentenceTransformer
from core.config import settings


class EmbeddingService:
    def __init__(self):
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL)

    def embed(self, text: str) -> List[float]:
        embedding = self.model.encode(text.strip())
        return embedding.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode([t.strip() for t in texts])
        return embeddings.tolist()

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        import numpy as np
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))


def compute_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[Tuple[str, str]]:
    lines = text.split('\n')
    chunks = []
    current_chunk = []
    current_heading = ""
    current_length = 0

    for line in lines:
        heading_match = re.match(r'^(#+)\s+(.+)', line)
        if heading_match:
            current_heading = f"{heading_match.group(2)}"

        line_length = len(line)
        if current_length + line_length > chunk_size and current_chunk:
            chunk_text = '\n'.join(current_chunk)
            chunks.append((chunk_text, current_heading))
            overlap_lines = current_chunk[-(overlap // 20):]
            current_chunk = overlap_lines
            current_length = sum(len(l) for l in current_chunk)
        else:
            current_chunk.append(line)
            current_length += line_length

    if current_chunk:
        chunk_text = '\n'.join(current_chunk)
        chunks.append((chunk_text, current_heading))

    return chunks


embedding_service = EmbeddingService()
