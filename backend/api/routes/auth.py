"""
OAuth2 / SSO routes.

  GET  /api/v1/auth/login    → redirect to Google consent screen
  GET  /api/v1/auth/callback → exchange code, verify @domain, set httpOnly cookie
                               → redirect to frontend
  GET  /api/v1/auth/me       → return current user's email (requires auth)
  POST /api/v1/auth/logout   → clear session cookie

Security notes:
  - JWT is stored in an httpOnly cookie — never exposed to JavaScript (XSS-safe).
  - OAuth `state` parameter lives in a short-lived httpOnly cookie (CSRF protection).
  - Email domain is enforced server-side; Google's `hd` param is a UI hint only.
  - Error messages never expose internal implementation details.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import db_session, require_auth
from core import auth as auth_utils
from core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

_STATE_COOKIE = "oauth_state"
_STATE_MAX_AGE_SECONDS = 300  # 5 minutes — enough time to complete the login flow


# ── cookie helpers ────────────────────────────────────────────────────────────


def _attach_session_cookie(
    response: RedirectResponse | JSONResponse, token: str
) -> None:
    """Write the JWT as a secure httpOnly session cookie onto `response`."""
    response.set_cookie(
        key=auth_utils.AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        max_age=settings.access_token_expire_minutes * 60,
        domain=settings.cookie_domain or None,
        path="/",
    )


def _clear_session_cookie(response: JSONResponse) -> None:
    """Remove the session cookie (logout)."""
    response.delete_cookie(
        key=auth_utils.AUTH_COOKIE_NAME,
        path="/",
        domain=settings.cookie_domain or None,
    )


# ── routes ────────────────────────────────────────────────────────────────────


@router.get(
    "/login",
    summary="Initiate Google OAuth2 login",
    status_code=status.HTTP_302_FOUND,
)
async def login() -> RedirectResponse:
    """Redirect the browser to the Google consent screen."""
    if settings.dev_bypass_auth:
        # Dev mode: issue a bypass JWT and redirect straight to the frontend
        jwt_token = auth_utils.create_access_token(
            email=f"dev@{settings.allowed_email_domain}",
            secret_key=settings.secret_key,
            expire_minutes=settings.access_token_expire_minutes,
        )
        frontend_callback = f"{settings.frontend_url.rstrip('/')}/auth/callback"
        response = RedirectResponse(
            frontend_callback, status_code=status.HTTP_302_FOUND
        )
        _attach_session_cookie(response, jwt_token)
        return response

    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured on this server.",
        )

    state = secrets.token_urlsafe(32)
    redirect_uri = auth_utils.callback_redirect_uri(settings.oauth_redirect_base_url)
    google_url = auth_utils.build_google_auth_url(
        client_id=settings.google_client_id,
        redirect_uri=redirect_uri,
        state=state,
        hd_hint=settings.allowed_email_domain,
    )

    response = RedirectResponse(google_url, status_code=status.HTTP_302_FOUND)
    # Store state in a short-lived httpOnly cookie for CSRF verification at callback
    response.set_cookie(
        _STATE_COOKIE,
        state,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=_STATE_MAX_AGE_SECONDS,
        path="/",
    )
    return response


@router.get(
    "/callback",
    summary="OAuth2 callback — Google redirects here after consent",
    status_code=status.HTTP_302_FOUND,
    include_in_schema=False,  # Hide raw OAuth callback from public API docs
)
async def oauth_callback(
    request: Request,
    code: str,
    state: str,
    session: AsyncSession = Depends(db_session),
) -> RedirectResponse:
    """
    Exchange authorization code for tokens, enforce email domain restriction,
    issue a signed JWT stored as an httpOnly session cookie, redirect to frontend.
    """
    # ── CSRF check ────────────────────────────────────────────────────────────
    stored_state = request.cookies.get(_STATE_COOKIE)
    if not stored_state or not secrets.compare_digest(stored_state, state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request. Please try logging in again.",
        )

    # ── Token exchange + userinfo fetch ───────────────────────────────────────
    redirect_uri = auth_utils.callback_redirect_uri(settings.oauth_redirect_base_url)
    try:
        tokens = await auth_utils.exchange_code_for_tokens(
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            code=code,
            redirect_uri=redirect_uri,
        )
        userinfo = await auth_utils.fetch_google_userinfo(tokens["access_token"])
    except Exception:
        # Never surface upstream provider errors to the client
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Authentication failed. Please try again.",
        )

    # ── Domain enforcement ────────────────────────────────────────────────────
    email: str = userinfo.get("email", "")
    if not email.lower().endswith(f"@{settings.allowed_email_domain.lower()}"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access is restricted to @{settings.allowed_email_domain} accounts.",
        )

    # ── Provision quota on first login ────────────────────────────────────────
    if not settings.bypass_quota:
        from models.user_quota import UserQuota

        q = await session.get(UserQuota, email)
        if q is None:
            session.add(UserQuota(email=email, page_quota=settings.default_page_quota, pages_used=0))
            await session.commit()

    # ── Issue session cookie ──────────────────────────────────────────────────
    jwt_token = auth_utils.create_access_token(
        email=email,
        secret_key=settings.secret_key,
        expire_minutes=settings.access_token_expire_minutes,
    )

    # Token travels ONLY as a Set-Cookie header — never in the redirect URL
    frontend_callback = f"{settings.frontend_url.rstrip('/')}/auth/callback"
    response = RedirectResponse(frontend_callback, status_code=status.HTTP_302_FOUND)
    _attach_session_cookie(response, jwt_token)
    response.delete_cookie(_STATE_COOKIE, path="/")
    return response


@router.get("/me", summary="Return the current user's email")
async def me(email: str = Depends(require_auth)) -> dict:
    """Returns the authenticated user's profile. Used by the frontend to validate session."""
    return {"email": email}


@router.get("/quota", summary="Return the current user's page quota")
async def quota(
    email: str = Depends(require_auth),
    session: AsyncSession = Depends(db_session),
) -> dict:
    from models.user_quota import UserQuota

    if settings.bypass_quota:
        return {"bypassed": True, "pages_used": 0, "page_quota": 0, "pages_remaining": 0}

    q = await session.get(UserQuota, email)
    pages_used = q.pages_used if q else 0
    page_quota = q.page_quota if q else settings.default_page_quota
    return {
        "bypassed": False,
        "pages_used": pages_used,
        "page_quota": page_quota,
        "pages_remaining": max(0, page_quota - pages_used),
    }


@router.post(
    "/logout", summary="Clear the session cookie", status_code=status.HTTP_200_OK
)
async def logout() -> JSONResponse:
    """Log the user out by clearing the session cookie."""
    response = JSONResponse({"message": "Logged out."})
    _clear_session_cookie(response)
    return response
