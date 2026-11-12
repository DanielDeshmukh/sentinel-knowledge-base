import asyncio
import secrets
import unittest
from datetime import datetime

from pydantic import ValidationError

from api.routes import register
from models.schemas import UserCreate, UserResponse
from services.auth import verify_password


class EmptyQuery:
    def filter(self, _criterion):
        return self

    def first(self):
        return None


class FakeSession:
    def query(self, _model):
        return EmptyQuery()

    def add(self, user):
        self.user = user

    def commit(self):
        pass

    def refresh(self, _user):
        pass


class UserDisplayNameSchemaTests(unittest.TestCase):
    def test_registration_requires_display_name(self):
        with self.assertRaises(ValidationError):
            UserCreate.model_validate({
                "email": "ken.rosenberg@example.com",
                "password": secrets.token_urlsafe(24),
            })

    def test_registration_rejects_blank_display_name(self):
        with self.assertRaises(ValidationError):
            UserCreate.model_validate({
                "display_name": "   ",
                "email": "ken.rosenberg@example.com",
                "password": secrets.token_urlsafe(24),
            })

    def test_registration_preserves_display_name(self):
        user = UserCreate.model_validate({
            "display_name": "Ken Rosenberg",
            "email": "ken.rosenberg@example.com",
            "password": secrets.token_urlsafe(24),
        })

        self.assertEqual(user.model_dump().get("display_name"), "Ken Rosenberg")

    def test_user_response_exposes_display_name(self):
        response = UserResponse.model_validate({
            "id": "test-user-id",
            "display_name": "Ken Rosenberg",
            "email": "ken.rosenberg@example.com",
            "role": "public",
            "approved": True,
            "created_at": datetime(2026, 1, 1),
        })

        self.assertEqual(response.model_dump().get("display_name"), "Ken Rosenberg")

    def test_registration_persists_name_and_hashes_password(self):
        password = secrets.token_urlsafe(24)
        payload = UserCreate(
            display_name="Ken Rosenberg",
            email="ken.rosenberg@example.com",
            password=password,
        )
        db = FakeSession()
        asyncio.run(register(payload, db=db))

        self.assertEqual(getattr(db.user, "display_name", None), "Ken Rosenberg")
        self.assertTrue(verify_password(password, db.user.password_hash))


if __name__ == "__main__":
    unittest.main()
