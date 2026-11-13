import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.retrieval import retrieve_chunks


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.statement = None
        self.parameters = None

    def execute(self, statement, parameters):
        self.statement = statement
        self.parameters = parameters
        return FakeResult(self.rows)


class RetrievalTests(unittest.TestCase):
    def test_permission_filtered_pgvector_search_limits_inside_sql(self):
        db = FakeSession([
            SimpleNamespace(
                id="weaker", document_id="doc-1", text="weaker match",
                heading_path=None, content_hash="hash-1",
                similarity=0.8, document_title="First",
            ),
            SimpleNamespace(
                id="stronger", document_id="doc-2", text="stronger match",
                heading_path="Heading", content_hash="hash-2",
                similarity=0.95, document_title="Second",
            ),
            SimpleNamespace(
                id="irrelevant", document_id="doc-3", text="unrelated",
                heading_path=None, content_hash="hash-3",
                similarity=0.2, document_title="Third",
            ),
        ])
        user = SimpleNamespace(role="public")

        with (
            patch("services.retrieval.embedding_service.embed", return_value=[1.0, 0.0]),
            patch("services.retrieval.settings.SIMILARITY_THRESHOLD", 0.5),
        ):
            chunks = retrieve_chunks(db, "question", user, top_k=1)

        self.assertEqual(
            [chunk["chunk_id"] for chunk in chunks],
            ["weaker", "stronger", "irrelevant"],
        )
        self.assertEqual(db.parameters["user_role"], "public")
        self.assertEqual(db.parameters["top_k"], 1)
        self.assertEqual(db.parameters["threshold"], 0.5)
        self.assertIn(":user_role = ANY(c.allowed_roles)", str(db.statement))
        self.assertIn("1 - (c.embedding <=> CAST(:embedding AS vector(384)))", str(db.statement))
        self.assertIn("ORDER BY c.embedding <=> CAST(:embedding AS vector(384))", str(db.statement))
        self.assertIn("LIMIT :top_k", str(db.statement))


if __name__ == "__main__":
    unittest.main()
