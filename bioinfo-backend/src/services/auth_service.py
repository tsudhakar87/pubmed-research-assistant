"""
Auth service: Google OAuth token verification and internal JWT issue/verify.

Flow:
  1. Frontend redirects user to Google sign-in.
  2. Frontend receives a Google ID token (credential from GIS One Tap / OAuth popup).
  3. Frontend POSTs the token to POST /api/v1/auth/google.
  4. We verify the Google ID token server-side, upsert the User row, and issue
     our own short-lived JWT.
  5. Every subsequent request carries the JWT as  Authorization: Bearer <token>.
  6. get_current_user() dependency validates the JWT and returns the User.
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

try:
    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests as google_requests
    _GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    _GOOGLE_AUTH_AVAILABLE = False

from ..utils.error_handlers import AuthError
from ..config.settings import settings

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

JWT_SECRET: str = os.environ.get("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRY_HOURS: int = 24
# Google's iat/nbf can be a few seconds ahead of our clock, which otherwise
# fails verification with "Token used too early".
GOOGLE_CLOCK_SKEW_SECONDS: int = 10
GOOGLE_CLIENT_ID: str = os.environ.get("GOOGLE_CLIENT_ID", "")

_bearer_scheme = HTTPBearer(auto_error=False)


# ── Google ID token verification ─────────────────────────────────────────────

def verify_google_token(id_token: str) -> dict:
    """
    Verify a Google ID token and return the decoded claims.
    Raises AuthError on failure.
    """
    if not _GOOGLE_AUTH_AVAILABLE:
        raise AuthError("Google auth library not installed")

    if not GOOGLE_CLIENT_ID:
        raise AuthError("GOOGLE_CLIENT_ID not configured")

    try:
        claims = google_id_token.verify_oauth2_token(
            id_token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=GOOGLE_CLOCK_SKEW_SECONDS,
        )
    except ValueError as e:
        logger.warning("Google token verification failed", extra={"error": str(e)})
        raise AuthError(f"Invalid Google token: {e}")

    if not claims.get("email") or not claims.get("email_verified", False):
        raise AuthError("Google account email is missing or unverified")
    return claims


# ── Internal JWT ─────────────────────────────────────────────────────────────

def create_access_token(user_id: UUID, email: str, name: Optional[str] = None) -> str:
    """Issue a signed JWT for the given user."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "name": name,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate our JWT. Raises AuthError on failure."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise AuthError(f"Invalid token: {e}")


# ── FastAPI dependency ────────────────────────────────────────────────────────

class TokenPayload:
    """Thin wrapper around decoded JWT claims."""
    def __init__(self, payload: dict):
        self.user_id: UUID = UUID(payload["sub"])
        self.email: str = payload["email"]
        self.name: Optional[str] = payload.get("name")


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> TokenPayload:
    """
    FastAPI dependency that validates the Bearer JWT and returns the token payload.
    Raises 401 if the token is missing or invalid.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(credentials.credentials)
        return TokenPayload(payload)
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (KeyError, ValueError):
        # Signature was valid but the claims are malformed (missing sub/email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Optional[TokenPayload]:
    """Like get_current_user but returns None instead of raising if no token."""
    if not credentials:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        return TokenPayload(payload)
    except (AuthError, KeyError, ValueError):
        return None
