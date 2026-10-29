"""
Auth routes:
  POST /api/v1/auth/google  — exchange Google ID token for our JWT
  GET  /api/v1/auth/me      — return current user info from JWT
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from ...services.auth_service import (
    create_access_token,
    get_current_user,
    verify_google_token,
    TokenPayload,
)
from ...services.cloud_sql_client import get_session, is_db_available
from ...models.database_models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"])


# ── Request / response models ─────────────────────────────────────────────────

class GoogleAuthRequest(BaseModel):
    id_token: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400  # 24 hours in seconds
    user: "UserInfo"


class UserInfo(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    picture_url: Optional[str] = None


AuthResponse.model_rebuild()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _upsert_user(claims: dict) -> User:
    """Find or create a User row from Google ID token claims."""
    email: str = claims["email"]
    google_sub: str = claims["sub"]
    name: Optional[str] = claims.get("name")
    picture: Optional[str] = claims.get("picture")

    if not is_db_available():
        # DB not configured — return an ephemeral user object without persisting
        import uuid
        u = User()
        u.id = uuid.uuid4()
        u.email = email
        u.google_sub = google_sub
        u.name = name
        u.picture_url = picture
        return u

    async with get_session() as session:
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(User).where(User.google_sub == google_sub)
        )
        user = result.scalar_one_or_none()

        if user is None:
            # Fall back to email so a row created without (or with a different)
            # google_sub doesn't trip the unique email constraint and 500.
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

        if user is None:
            user = User(
                email=email,
                google_sub=google_sub,
                name=name,
                picture_url=picture,
                last_login=now,
            )
            session.add(user)
        else:
            user.google_sub = google_sub
            user.email = email
            user.name = name
            user.picture_url = picture
            user.last_login = now
        await session.flush()

    return user


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/google", response_model=AuthResponse)
async def google_auth(body: GoogleAuthRequest) -> AuthResponse:
    """
    Exchange a Google ID token for our application JWT.
    The frontend should send the credential from Google Identity Services.
    """
    claims = verify_google_token(body.id_token)
    user = await _upsert_user(claims)
    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        name=user.name,
    )
    logger.info("User authenticated", extra={"email": user.email})
    return AuthResponse(
        access_token=access_token,
        user=UserInfo(
            id=str(user.id),
            email=user.email,
            name=user.name,
            picture_url=user.picture_url,
        ),
    )


@router.get("/me", response_model=UserInfo)
async def get_me(current_user: TokenPayload = Depends(get_current_user)) -> UserInfo:
    """Return the currently authenticated user's info from the JWT."""
    return UserInfo(
        id=str(current_user.user_id),
        email=current_user.email,
        name=current_user.name,
    )
