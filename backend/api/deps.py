"""
FastAPI dependency providers.

require_auth:
  Extracts and validates the JWT session from:
    1. httpOnly session cookie (browser clients after OAuth)
    2. Authorization: Bearer <token> header (API clients, testing)
  Returns the authenticated user's email on success.
  If DEV_BYPASS_AUTH=true, skips all checks (local dev only).

db_session:
  Yields an async SQLAlchemy session, cleaned up after each request.
"""

from typing import AsyncGenerator

import jwt as pyjwt
from fastapi import HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core import auth as auth_utils
from core.config import settings
from core.database import get_session

# auto_error=False so we can fall back to the cookie without FastAPI raising 403
_bearer = HTTPBearer(auto_error=False)


def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> str:
    """
    Authenticate the request.

    Checks, in order:
      1. DEV_BYPASS_AUTH env var (dev only — never in production)
      2. httpOnly session cookie (browser OAuth flow)
      3. Authorization: Bearer <jwt> header (API clients)

    Returns the authenticated user's email (str).
    Raises HTTP 401 / 403 on failure.
    """
    if settings.dev_bypass_auth:
        return f"dev@{settings.allowed_email_domain}"

    # Prefer cookie (browser) → fallback to Bearer header (API clients / curl)
    raw_token: str | None = request.cookies.get(auth_utils.AUTH_COOKIE_NAME)
    if not raw_token and credentials:
        raw_token = credentials.credentials

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        email = auth_utils.decode_access_token(raw_token, settings.secret_key)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except pyjwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Re-enforce domain on every request — not just at login time
    if not email.lower().endswith(f"@{settings.allowed_email_domain.lower()}"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access restricted to @{settings.allowed_email_domain} accounts.",
        )

    return email


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session
