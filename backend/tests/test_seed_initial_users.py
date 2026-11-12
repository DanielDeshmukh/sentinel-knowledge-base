import secrets
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.database import Base
from models.document import Document
from models.user import User
from services.auth import hash_password, verify_password
from seed_initial_users import SeedConflict, seed_initial_users


PASSWORDS = {
    "tommy.vercetti@example.com": secrets.token_urlsafe(24),
    "ken.rosenberg@example.com": secrets.token_urlsafe(24),
    "lance.vance@example.com": secrets.token_urlsafe(24),
    "sonny.forelli@example.com": secrets.token_urlsafe(24),
}


class SeedInitialUsersTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine, tables=[User.__table__])
        self.db = Session(self.engine)
        self.db.add(User(
            id="legacy-admin-id",
            email="admin@sentinel.local",
            display_name="Local Administrator",
            password_hash=hash_password(secrets.token_urlsafe(24)),
            role="admin",
            approved=True,
        ))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_bootstrap_renames_admin_and_creates_public_users(self):
        seed_initial_users(self.db, PASSWORDS)
        users = {user.email: user for user in self.db.query(User).all()}

        self.assertEqual(len(users), 4)
        self.assertEqual(users["tommy.vercetti@example.com"].id, "legacy-admin-id")
        self.assertEqual(users["tommy.vercetti@example.com"].display_name, "Tommy Vercetti")
        self.assertEqual(users["tommy.vercetti@example.com"].role, "admin")
        self.assertEqual(users["ken.rosenberg@example.com"].display_name, "Ken Rosenberg")
        self.assertEqual(users["ken.rosenberg@example.com"].role, "public")
        for email, password in PASSWORDS.items():
            self.assertTrue(verify_password(password, users[email].password_hash))

    def test_rerun_does_not_reset_passwords(self):
        seed_initial_users(self.db, PASSWORDS)
        original_hash = self.db.query(User).filter_by(
            email="ken.rosenberg@example.com"
        ).one().password_hash
        changed_passwords = {
            email: secrets.token_urlsafe(24) for email in PASSWORDS
        }

        seed_initial_users(self.db, changed_passwords)
        current_hash = self.db.query(User).filter_by(
            email="ken.rosenberg@example.com"
        ).one().password_hash

        self.assertEqual(current_hash, original_hash)

    def test_email_collision_rolls_back(self):
        self.db.add(User(
            id="unrelated-id",
            email="ken.rosenberg@example.com",
            display_name="Unrelated Account",
            password_hash=hash_password(secrets.token_urlsafe(24)),
            role="public",
            approved=True,
        ))
        self.db.commit()

        with self.assertRaises(SeedConflict):
            seed_initial_users(self.db, PASSWORDS)
        self.db.rollback()

        self.assertIsNotNone(self.db.query(User).filter_by(
            email="admin@sentinel.local"
        ).first())
        self.assertIsNone(self.db.query(User).filter_by(
            email="lance.vance@example.com"
        ).first())

    def test_unapproved_existing_account_blocks_bootstrap(self):
        self.db.add(User(
            id="unapproved-ken-id",
            email="ken.rosenberg@example.com",
            display_name="Ken Rosenberg",
            password_hash=hash_password(secrets.token_urlsafe(24)),
            role="public",
            approved=False,
        ))
        self.db.commit()

        with self.assertRaises(SeedConflict):
            seed_initial_users(self.db, PASSWORDS)

        self.assertIsNotNone(self.db.query(User).filter_by(
            email="admin@sentinel.local"
        ).first())
        self.assertFalse(self.db.query(User).filter_by(
            email="ken.rosenberg@example.com"
        ).one().approved)
        self.assertIsNone(self.db.query(User).filter_by(
            email="lance.vance@example.com"
        ).first())


if __name__ == "__main__":
    unittest.main()
