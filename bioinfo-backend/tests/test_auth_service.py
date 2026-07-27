"""Unit tests for JWT auth service."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import uuid
import pytest

from src.services.auth_service import (
    create_access_token,
    decode_access_token,
)
from src.utils.error_handlers import AuthError


class TestJWT:
    def test_create_and_decode(self):
        user_id = uuid.uuid4()
        token = create_access_token(user_id=user_id, email="test@example.com", name="Test User")
        payload = decode_access_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["email"] == "test@example.com"
        assert payload["name"] == "Test User"

    def test_invalid_token_raises_auth_error(self):
        with pytest.raises(AuthError):
            decode_access_token("not.a.valid.token")

    def test_tampered_token_raises_auth_error(self):
        user_id = uuid.uuid4()
        token = create_access_token(user_id=user_id, email="test@example.com")
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(AuthError):
            decode_access_token(tampered)
