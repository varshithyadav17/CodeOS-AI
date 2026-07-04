"""Auth routes: signup, login, google session, me, logout.

The original implementation called an external demo backend to verify a
Google session. As part of the standalone migration that runtime dependency
was removed; the `/auth/google` endpoint stays in place (so the frontend
contract is unchanged) but it now responds with **501 Not Implemented**
until valid `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` are configured.

JWT email / password authentication (signup + login + me + logout) is fully
wired and is the recommended path until you wire up real Google OAuth.

Tokens are issued **both** as a JSON `token` field (for curl / tests /
programmatic clients) and as an HttpOnly cookie (used by the browser
frontend, XSS-resistant).
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr

from ..deps import get_auth_service, get_current_user
from ...services.auth_service import AuthService
from ...core.config import settings
from ...core.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupIn(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class GoogleIn(BaseModel):
    session_id: str


def _set_auth_cookie(response: Response, token: str) -> None:
    """Issue the auth cookie alongside the JSON token field."""
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        max_age=settings.JWT_EXPIRY_HOURS * 3600,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )


@router.post("/signup")
async def signup(
    body: SignupIn,
    response: Response,
    svc: AuthService = Depends(get_auth_service),
):
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    token, user = await svc.signup(body.email, body.password, body.name)
    _set_auth_cookie(response, token)
    return {"token": token, "user": user.model_dump(exclude={"password_hash"})}


@router.post("/login")
async def login(
    body: LoginIn,
    response: Response,
    svc: AuthService = Depends(get_auth_service),
):
    token, user = await svc.login(body.email, body.password)
    _set_auth_cookie(response, token)
    return {"token": token, "user": user.model_dump(exclude={"password_hash"})}


@router.post("/google")
async def google(body: GoogleIn, svc: AuthService = Depends(get_auth_service)):
    """Exchange a Google OAuth session for our JWT.

    Placeholder until standalone Google OAuth credentials are supplied.
    Configure ``GOOGLE_CLIENT_ID`` and ``GOOGLE_CLIENT_SECRET`` in
    ``backend/.env`` to enable this flow.
    """
    if not (settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                "Google sign-in is not configured yet. Set GOOGLE_CLIENT_ID "
                "and GOOGLE_CLIENT_SECRET in backend/.env to enable it. "
                "Please use the email / password form in the meantime."
            ),
        )
    # When credentials are supplied, implement the standard OAuth 2.0
    # token-exchange here (e.g. via google-auth / google-auth-oauthlib).
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Standalone Google OAuth flow not yet implemented.",
    )


@router.post("/logout")
async def logout(response: Response):
    """Clear the auth cookie. Always succeeds — idempotent."""
    response.delete_cookie(
        key=settings.COOKIE_NAME,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )
    return {"ok": True}


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {"user": user.model_dump(exclude={"password_hash"})}
