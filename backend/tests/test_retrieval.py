import unittest
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from services.retrieval import build_retrieval_query, handle_chat, retrieve_chunks


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
    def test_contextualizes_follow_up_questions_with_the_last_exchange(self):
        query = build_retrieval_query(
            "Why was it even enforced in the first place?",
            [
                {"role": "user", "content": "What are the key principles of the DPDP Act?"},
                {"role": "assistant", "content": "The Act protects digital personal data and sets duties for fiduciaries."},
            ],
        )

        self.assertIn("What are the key principles of the DPDP Act?", query)
        self.assertIn("sets duties for fiduciaries", query)
        self.assertIn("Why was it even enforced in the first place?", query)

    def test_keeps_standalone_questions_independent_of_old_context(self):
        query = build_retrieval_query(
            "How quickly should a cyber incident be reported to CERT-In?",
            [
                {"role": "user", "content": "What are the key principles of the DPDP Act?"},
                {"role": "assistant", "content": "The Act protects digital personal data."},
            ],
        )

        self.assertEqual(query, "How quickly should a cyber incident be reported to CERT-In?")

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
        self.assertIn("d.sync_state = 'searchable'", str(db.statement))
        self.assertIn("1 - (c.embedding <=> CAST(:embedding AS vector(384)))", str(db.statement))
        self.assertIn("ORDER BY c.embedding <=> CAST(:embedding AS vector(384))", str(db.statement))
        self.assertIn("LIMIT :top_k", str(db.statement))


class ChatRetrievalContextTests(unittest.TestCase):
    def test_chat_passes_history_to_permission_filtered_vector_retrieval(self):
        history = [
            {"role": "user", "content": "What are the key principles of the DPDP Act?"},
            {"role": "assistant", "content": "It protects personal data and establishes fiduciary duties."},
        ]
        user = SimpleNamespace(role="admin")
        with patch("services.retrieval.run_in_threadpool", new_callable=AsyncMock) as retrieve:
            retrieve.return_value = []
            asyncio.run(handle_chat(SimpleNamespace(), "Why was it enforced?", history, user))

        self.assertIs(retrieve.await_args.args[0], retrieve_chunks)
        self.assertEqual(retrieve.await_args.args[2], "Why was it enforced?")
        self.assertEqual(retrieve.await_args.args[5], history)


if __name__ == "__main__":
    unittest.main()
