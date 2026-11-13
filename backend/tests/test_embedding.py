import unittest
from unittest.mock import Mock, patch

from core.config import settings
from services.embedding import EmbeddingService, compute_content_hash, chunk_text


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class EmbeddingServiceTests(unittest.TestCase):
    def test_query_embedding_uses_nvidia_query_mode(self):
        response = FakeResponse({"data": [{"index": 0, "embedding": [0.1, 0.2]}]})
        httpx = Mock(post=Mock(return_value=response))
        service = EmbeddingService()

        with (
            patch("services.embedding.httpx", httpx, create=True),
            patch.object(settings, "NVIDIA_API_KEY", "nvidia-test-key"),
            patch.object(settings, "EMBEDDING_DIMENSION", 2),
        ):
            embedding = service.embed("question text")

        self.assertEqual(embedding, [0.1, 0.2])
        request = httpx.post.call_args
        self.assertEqual(request.args[0], settings.NVIDIA_EMBEDDING_API_URL)
        self.assertEqual(request.kwargs["json"]["input_type"], "query")
        self.assertEqual(request.kwargs["json"]["input"], ["question text"])
        self.assertEqual(request.kwargs["json"]["dimensions"], 2)
        self.assertEqual(request.kwargs["headers"]["Authorization"], "Bearer nvidia-test-key")

    def test_passage_batch_preserves_input_order_and_uses_passage_mode(self):
        response = FakeResponse({"data": [
            {"index": 1, "embedding": [0.3, 0.4]},
            {"index": 0, "embedding": [0.1, 0.2]},
        ]})
        httpx = Mock(post=Mock(return_value=response))
        service = EmbeddingService()

        with (
            patch("services.embedding.httpx", httpx, create=True),
            patch.object(settings, "NVIDIA_API_KEY", "nvidia-test-key"),
            patch.object(settings, "EMBEDDING_DIMENSION", 2),
        ):
            embeddings = service.embed_batch(["first passage", "second passage"])

        self.assertEqual(embeddings, [[0.1, 0.2], [0.3, 0.4]])
        request = httpx.post.call_args
        self.assertEqual(request.kwargs["json"]["input_type"], "passage")
        self.assertEqual(request.kwargs["json"]["input"], ["first passage", "second passage"])

    def test_missing_provider_key_fails_closed(self):
        service = EmbeddingService()
        with patch.object(settings, "NVIDIA_API_KEY", ""):
            with self.assertRaisesRegex(RuntimeError, "NVIDIA_API_KEY"):
                service.embed("question text")

    def test_content_hash_and_chunking_remain_stable(self):
        self.assertEqual(len(compute_content_hash("text")), 64)
        self.assertEqual(compute_content_hash("text"), compute_content_hash("text"))
        self.assertEqual(chunk_text("# Title\n\nText"), [("# Title\n\nText", "Title")])


if __name__ == "__main__":
    unittest.main()
