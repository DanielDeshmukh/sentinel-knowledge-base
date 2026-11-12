import os
import unittest

from sqlalchemy import create_engine, text

import init_db


class UserSchemaUpgradeTests(unittest.TestCase):
    def test_upgrade_function_is_available(self):
        self.assertTrue(callable(getattr(init_db, "upgrade_user_schema", None)))

    @unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "requires disposable PostgreSQL")
    def test_upgrade_backfills_existing_users_and_is_idempotent(self):
        engine = create_engine(os.environ["TEST_DATABASE_URL"])
        try:
            with engine.begin() as connection:
                connection.execute(text("""
                    CREATE TEMPORARY TABLE users (
                        id VARCHAR PRIMARY KEY,
                        email VARCHAR NOT NULL,
                        password_hash VARCHAR NOT NULL,
                        role VARCHAR NOT NULL,
                        approved BOOLEAN NOT NULL,
                        created_at TIMESTAMP NOT NULL
                    )
                """))
                connection.execute(text("""
                    INSERT INTO users (id, email, password_hash, role, approved, created_at)
                    VALUES (
                        'legacy-id',
                        'ada.lovelace@example.com',
                        'hash',
                        'public',
                        TRUE,
                        CURRENT_TIMESTAMP
                    )
                """))

                init_db.upgrade_user_schema(connection)
                self.assertEqual(
                    connection.execute(text(
                        "SELECT display_name FROM users WHERE id = 'legacy-id'"
                    )).scalar_one(),
                    "Ada Lovelace",
                )

                connection.execute(text(
                    "UPDATE users SET display_name = 'Preserved Name' WHERE id = 'legacy-id'"
                ))
                init_db.upgrade_user_schema(connection)
                self.assertEqual(
                    connection.execute(text(
                        "SELECT display_name FROM users WHERE id = 'legacy-id'"
                    )).scalar_one(),
                    "Preserved Name",
                )
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
