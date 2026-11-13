import unittest
from types import SimpleNamespace
from unittest.mock import patch

from init_db import upgrade_embedding_schema


class FakeResult:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def fetchall(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class FakeConnection:
    def __init__(self):
        self.applied = False
        self.updates = []
        self.statements = []
        self.rows = {
            "chunks": [SimpleNamespace(id="chunk-1", text="old chunk")],
            "staging_chunks": [SimpleNamespace(id="stage-1", text="old staged chunk")],
        }

    def execute(self, statement, parameters=None):
        sql = str(statement)
        self.statements.append((sql, parameters or {}))
        if "SELECT 1 FROM sentinel_schema_migrations" in sql:
            return FakeResult([("applied",)] if self.applied else [])
        if "information_schema.columns" in sql:
            return FakeResult([("_int4",)])
        if "SELECT id, text FROM chunks" in sql:
            rows = self.rows["chunks"]
            return FakeResult(sorted(
                (row for row in rows if row.id > parameters["last_id"]),
                key=lambda row: row.id,
            )[:parameters["batch_size"]])
        if "SELECT id, text FROM staging_chunks" in sql:
            rows = self.rows["staging_chunks"]
            return FakeResult(sorted(
                (row for row in rows if row.id > parameters["last_id"]),
                key=lambda row: row.id,
            )[:parameters["batch_size"]])
        if sql.lstrip().startswith("UPDATE chunks"):
            self.updates.append(("chunks", parameters))
        if sql.lstrip().startswith("UPDATE staging_chunks"):
            self.updates.append(("staging_chunks", parameters))
        if "INSERT INTO sentinel_schema_migrations" in sql:
            self.applied = True
        return FakeResult()


class EmbeddingMigrationTests(unittest.TestCase):
    def test_rebuilds_existing_and_staged_vectors_once(self):
        connection = FakeConnection()
        with patch(
            "init_db.embedding_service.embed_batch",
            side_effect=lambda texts: [[float(len(texts)), float(len(text))] for text in texts],
        ) as embed_batch, patch("init_db.settings.NVIDIA_API_KEY", "nvidia-test-key"):
            upgrade_embedding_schema(connection)
            upgrade_embedding_schema(connection)

        self.assertEqual(len(connection.updates), 2)
        self.assertEqual(
            {table for table, _parameters in connection.updates},
            {"chunks", "staging_chunks"},
        )
        self.assertEqual(embed_batch.call_count, 2)
        sql_text = "\n".join(sql for sql, _parameters in connection.statements)
        self.assertIn("TYPE vector(384)", sql_text)
        self.assertTrue(connection.applied)

    def test_rebuilds_rows_in_bounded_batches(self):
        connection = FakeConnection()
        connection.rows["chunks"] = [
            SimpleNamespace(id=f"chunk-{index:03d}", text=f"chunk body {index}")
            for index in range(205)
        ]
        connection.rows["staging_chunks"] = []

        with patch(
            "init_db.embedding_service.embed_batch",
            side_effect=lambda texts: [[float(len(texts))] for _ in texts],
        ) as embed_batch, patch("init_db.settings.NVIDIA_API_KEY", "nvidia-test-key"):
            upgrade_embedding_schema(connection)

        self.assertEqual(embed_batch.call_count, 3)
        self.assertEqual(len(connection.updates), 205)
        self.assertEqual(
            [len(call.args[0]) for call in embed_batch.call_args_list],
            [100, 100, 5],
        )

    def test_fails_migration_without_nvidia_key(self):
        connection = FakeConnection()
        with patch("init_db.settings.NVIDIA_API_KEY", ""):
            with self.assertRaisesRegex(RuntimeError, "NVIDIA_API_KEY"):
                upgrade_embedding_schema(connection)

        self.assertFalse(connection.applied)
        self.assertEqual(connection.updates, [])
        self.assertFalse(any("ALTER TABLE" in sql for sql, _parameters in connection.statements))


if __name__ == "__main__":
    unittest.main()
