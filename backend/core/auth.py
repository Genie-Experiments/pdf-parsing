"""
Google OAuth2 / OIDC helpers and JWT utilities.

Auth flow:
  1. GET /auth/login  → 302 → Google consent screen
  2. Google           → 302 → GET /auth/callback?code=...&state=...
  3. /auth/callback   → exchange code → fetch userinfo → verify @domain
                      → issue signed JWT → set httpOnly cookie
                      → 302 → frontend home
  4. All API routes   → cookie (or Authorization: Bearer) → require_auth dep

Security properties:
  - JWT is stored in an httpOnly cookie (not accessible to JavaScript — XSS-safe).
  - CSRF is mitigated by SameSite=Lax (same-site requests only for state-changing ops).
  - OAuth state parameter (CSRF token) is stored in a short-lived httpOnly cookie.
  - Email domain is enforced server-side after every token decode, not just at login.
  - Tokens are short-lived (configurable via ACCESS_TOKEN_EXPIRE_MINUTES).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt  # PyJWT

# ── constants ─────────────────────────────────────────────────────────────────

AUTH_COOKIE_NAME = "access_token"

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
_ALGORITHM = "HS256"

# ── JWT ───────────────────────────────────────────────────────────────────────


def create_access_token(email: str, secret_key: str, expire_minutes: int) -> str:
    """Create a signed JWT containing the user's email."""
    payload = {
        "sub": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expire_minutes),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, secret_key, algorithm=_ALGORITHM)


def decode_access_token(token: str, secret_key: str) -> str:
    """
    Decode and verify a JWT. Returns the email (sub claim).
    Raises jwt.ExpiredSignatureError or jwt.InvalidTokenError on failure.
    """
    payload = jwt.decode(token, secret_key, algorithms=[_ALGORITHM])
    email: str = payload["sub"]
    return email


# ── Google OAuth2 ─────────────────────────────────────────────────────────────


def build_google_auth_url(
    client_id: str, redirect_uri: str, state: str, hd_hint: str
) -> str:
    """Build the Google authorization URL to redirect the user to."""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        # hd restricts the account chooser to the specified domain in Google's UI.
        # Domain is ALSO enforced server-side after token exchange.
        "hd": hd_hint,
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{_GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> dict:
    """Exchange an authorization code for Google access/id tokens."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def fetch_google_userinfo(access_token: str) -> dict:
    """Fetch the authenticated user's profile from Google userinfo endpoint."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()


def callback_redirect_uri(base_url: str) -> str:
    """Canonical OAuth callback URI — must match exactly what's registered in Google console."""
    return f"{base_url.rstrip('/')}/api/v1/auth/callback"
