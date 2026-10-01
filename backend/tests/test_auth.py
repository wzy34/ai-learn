from datetime import timedelta

import pytest

from app.core.auth import create_access_token, decode_access_token
from app.core.config import settings
from app.core.exceptions import AuthenticationError


@pytest.fixture
def jwt_settings(monkeypatch):
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "test-jwt-secret")
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")


def test_access_token_round_trip_preserves_user_identity(jwt_settings):
    token = create_access_token(user_id=42, openid="openid-42")

    identity = decode_access_token(token)

    assert identity.user_id == 42
    assert identity.openid == "openid-42"


def test_expired_access_token_is_rejected(jwt_settings):
    token = create_access_token(
        user_id=42,
        openid="openid-42",
        expires_delta=timedelta(seconds=-1),
    )

    with pytest.raises(AuthenticationError):
        decode_access_token(token)
