from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.exceptions import AuthenticationError
from app.core.logging import get_logger

logger = get_logger(__name__)

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")


@dataclass(frozen=True)
class AuthenticatedUser:
    """Identity decoded from a valid application access token."""

    user_id: int
    openid: str


def _get_jwt_secret() -> str:
    if not settings.JWT_SECRET_KEY:
        raise AuthenticationError(
            detail="JWT_SECRET_KEY is not configured",
            status_code=503,
        )
    return settings.JWT_SECRET_KEY


def create_access_token(
    user_id: int,
    openid: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create an expiring access token bound to one WeChat user."""

    expires_at = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=settings.JWT_EXPIRE_DAYS)
    )
    payload = {
        "user_id": user_id,
        "openid": openid,
        "exp": expires_at,
    }
    return jwt.encode(
        payload,
        _get_jwt_secret(),
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> AuthenticatedUser:
    """Decode a token while pinning the configured signing algorithm."""

    try:
        payload = jwt.decode(
            token,
            _get_jwt_secret(),
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError as error:
        raise AuthenticationError("Authentication token has expired") from error
    except jwt.InvalidTokenError as error:
        raise AuthenticationError() from error

    user_id = payload.get("user_id")
    openid = payload.get("openid")
    if not isinstance(user_id, int) or user_id <= 0 or not isinstance(openid, str) or not openid:
        raise AuthenticationError()

    return AuthenticatedUser(user_id=user_id, openid=openid)


async def get_required_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> AuthenticatedUser:
    """Require a valid bearer token for user-owned resources."""

    if credentials is None:
        raise AuthenticationError("Authentication token is required")

    return decode_access_token(credentials.credentials)


async def get_optional_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> AuthenticatedUser | None:
    """Associate core requests with a user when a valid token is supplied."""

    if credentials is None:
        return None

    try:
        return decode_access_token(credentials.credentials)
    except AuthenticationError as error:
        # Core learning remains available for an expired token, but the failed
        # association is observable instead of being silently ignored.
        logger.warning("Ignoring invalid optional authentication", detail=error.detail)
        return None
