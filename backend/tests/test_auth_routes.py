import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from api.routes import login
from models.schemas import AuthToken, UserLogin


class FakeQuery:
    def __init__(self, user):
        self.user = user

    def filter(self, _condition):
        return self

    def first(self):
        return self.user


class FakeDatabase:
    def __init__(self, user):
        self.user = user

    def query(self, _model):
        return FakeQuery(self.user)


class AuthRouteTests(unittest.TestCase):
    def test_login_returns_user_with_token_to_avoid_follow_up_me_request(self):
        user = SimpleNamespace(
            id="user-1",
            display_name="Sonny Forelli",
            email="sonny.forelli@example.com",
            role="restricted",
            requested_role=None,
            role_request_status="none",
            approved=True,
            created_at="2026-11-13T10:00:00",
            password_hash="hashed",
        )
        with (
            patch("api.routes.verify_password", return_value=True),
            patch("api.routes.create_access_token", return_value="signed-token"),
        ):
            payload = asyncio.run(login(
                UserLogin(email=user.email, password="not-asserted-here"),
                FakeDatabase(user),
            ))

        response = AuthToken.model_validate(payload)
        self.assertEqual(response.access_token, "signed-token")
        self.assertEqual(response.user.email, user.email)
        self.assertEqual(response.user.role, "restricted")


if __name__ == "__main__":
    unittest.main()
