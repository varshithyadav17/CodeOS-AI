"""Auth module — service, dependency injection, and routes."""
from __future__ import annotations
import logging
import hmac
import secrets
import time
import jwt
from google.auth import exceptions as google_exceptions
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from ..utils import blocking

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response

from ..config import settings
from .. import database as db
from ..database import get_user_repo, IMetadataRepository
from ..models import User
from ..schemas import SignupIn, LoginIn, GoogleIn
from ..security import hash_password, verify_password, create_token, decode_token

logger = logging.getLogger(__name__)
GOOGLE_COOKIE = "codeos_google_nonce"


def public_user(user):
    return user.model_dump(exclude={"password_hash", "google_subject"})


def verify_google_credential(credential):
    from google.oauth2 import id_token
    from google.auth.transport.requests import Request

    class BoundedRequest(Request):
        def __call__(self, *args, **kwargs):
            kwargs["timeout"] = 10
            return super().__call__(*args, **kwargs)

    return id_token.verify_oauth2_token(credential, BoundedRequest(), settings.GOOGLE_CLIENT_ID)

# ---------------------------------------------------------------------------
# AuthService
# ---------------------------------------------------------------------------

class AuthService:
    def __init__(self, users: IMetadataRepository):
        self.users = users

    async def signup(self, email: str, password: str, name: str) -> tuple[str, User]:
        existing = await self.users.find_one({"email": email.lower()})
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")
        user = User(
            email=email.lower(),
            name=name,
            password_hash=await blocking(hash_password, password),
            provider="local",
        )
        try:
            await self.users.insert(user)
        except IntegrityError:
            raise HTTPException(status_code=409, detail="Email already registered")
        return create_token(user.id, user.email), user

    async def login(self, email: str, password: str) -> tuple[str, User]:
        user = await self.users.find_one({"email": email.lower()})
        if not user or not user.password_hash or not await blocking(verify_password, password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return create_token(user.id, user.email), user

    async def upsert_google_user(self, claims: dict, link_password: str | None) -> tuple[str, User]:
        subject, email = claims["sub"], claims["email"].lower()
        existing = await self.users.find_one({"google_subject": subject})
        if existing:
            return create_token(existing.id, existing.email), existing
        try:
            async with db.get_engine().begin() as conn:
                row = (await conn.execute(select(db.users).where(db.users.c.email == email).with_for_update())).mappings().first()
                if row:
                    user = User(**row)
                    if user.google_subject and user.google_subject != subject:
                        raise HTTPException(409, "This email is already connected to another Google account.")
                    if not user.google_subject:
                        if user.password_hash:
                            if not link_password:
                                raise HTTPException(409, {"code": "google_link_required", "message": "Enter your existing CodeOS password to connect Google."})
                            if not await blocking(verify_password, link_password, user.password_hash):
                                raise HTTPException(401, "Incorrect CodeOS password. Google was not connected.")
                        elif not (user.provider == "google" and (email.endswith("@gmail.com") or claims.get("hd"))):
                            # An externally hosted email alone cannot migrate a legacy identity.
                            raise HTTPException(409, "This legacy account needs administrator-assisted identity recovery before Google can be connected.")
                        await conn.execute(update(db.users).where(db.users.c.id == user.id).values(google_subject=subject, updated_at=db.now()))
                        user.google_subject = subject
                else:
                    user = User(email=email, name=str(claims.get("name") or email.split("@")[0])[:120],
                        picture=claims.get("picture"), provider="google", google_subject=subject)
                    await conn.execute(insert(db.users).values(**user.model_dump(mode="json")))
        except IntegrityError:
            user = await self.users.find_one({"google_subject": subject})
            if not user:
                raise HTTPException(409, "Account changed during sign-in. Please try again.")
        return create_token(user.id, user.email), user

    async def get_by_id(self, user_id: str) -> User | None:
        return await self.users.get(user_id)


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

def _extract_token(authorization: str | None, cookie_token: str | None) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    if cookie_token:
        return cookie_token.strip()
    raise HTTPException(status_code=401, detail="Missing bearer token")


async def get_current_user(
    authorization: str | None = Header(default=None),
    codeos_token: str | None = Cookie(default=None, alias=settings.COOKIE_NAME),
) -> User:
    token = _extract_token(authorization, codeos_token)
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    users = get_user_repo()
    user = await users.get(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_auth_service() -> AuthService:
    return AuthService(get_user_repo())


# ---------------------------------------------------------------------------
# Cookie helper
# ---------------------------------------------------------------------------

def _set_auth_cookie(response: Response, token: str) -> None:
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


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup")
async def signup(
    body: SignupIn,
    response: Response,
    svc: AuthService = Depends(get_auth_service),
):
    token, user = await svc.signup(body.email, body.password, body.name)
    _set_auth_cookie(response, token)
    return {"token": token, "user": public_user(user)}


@router.post("/login")
async def login(
    body: LoginIn,
    response: Response,
    svc: AuthService = Depends(get_auth_service),
):
    token, user = await svc.login(body.email, body.password)
    _set_auth_cookie(response, token)
    return {"token": token, "user": public_user(user)}


@router.get("/google/challenge")
async def google_challenge(response: Response):
    """Runtime client configuration and a short-lived, browser-bound nonce."""
    if not settings.GOOGLE_CLIENT_ID:
        return {"enabled": False}
    nonce = secrets.token_urlsafe(32)
    challenge = jwt.encode({"sub": nonce, "iss": "codeos-ai", "aud": "codeos-google",
        "iat": int(time.time()), "exp": int(time.time()) + 600}, settings.JWT_SECRET, algorithm="HS256")
    response.set_cookie(GOOGLE_COOKIE, challenge, max_age=600, httponly=True,
        secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE, domain=settings.COOKIE_DOMAIN, path="/api/auth")
    return {"enabled": True, "client_id": settings.GOOGLE_CLIENT_ID, "nonce": nonce, "expires_in": 600}


@router.post("/google")
async def google(
    body: GoogleIn,
    response: Response,
    google_nonce: str | None = Cookie(default=None, alias=GOOGLE_COOKIE),
    svc: AuthService = Depends(get_auth_service),
):
    """Verify a Google ID token and exchange it for our JWT."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Google sign-in is currently unavailable. Use email sign-in.")
    try:
        challenge = jwt.decode(google_nonce or "", settings.JWT_SECRET, algorithms=["HS256"],
            audience="codeos-google", issuer="codeos-ai", options={"require": ["sub", "exp", "iat", "aud", "iss"]})
    except jwt.PyJWTError:
        raise HTTPException(401, "Google sign-in expired. Refresh sign-in and try again.")
    try:
        idinfo = await blocking(verify_google_credential, body.credential)
    except google_exceptions.TransportError:
        raise HTTPException(503, "Google sign-in is temporarily unavailable. Try again shortly.")
    except (ValueError, google_exceptions.GoogleAuthError):
        raise HTTPException(status_code=401, detail="Invalid Google credential")
    except Exception:
        logger.warning("Google verification service unavailable")
        raise HTTPException(503, "Google sign-in is temporarily unavailable. Try again shortly.")

    email = idinfo.get("email")
    if not isinstance(email, str) or idinfo.get("email_verified") is not True:
        raise HTTPException(status_code=401, detail="Google account email not verified")
    if not isinstance(idinfo.get("sub"), str) or not 1 <= len(idinfo["sub"]) <= 255:
        raise HTTPException(401, "Invalid Google account identifier")
    nonce = idinfo.get("nonce")
    if not isinstance(nonce, str) or not hmac.compare_digest(nonce.encode(), challenge["sub"].encode()):
        raise HTTPException(401, "Google sign-in does not match this browser. Refresh sign-in and try again.")
    token, user = await svc.upsert_google_user(idinfo, body.link_password.get_secret_value() if body.link_password else None)
    _set_auth_cookie(response, token)
    response.delete_cookie(GOOGLE_COOKIE, domain=settings.COOKIE_DOMAIN, path="/api/auth",
        secure=settings.COOKIE_SECURE, httponly=True, samesite=settings.COOKIE_SAMESITE)
    return {"token": token, "user": public_user(user)}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key=settings.COOKIE_NAME, domain=settings.COOKIE_DOMAIN, path="/",
        secure=settings.COOKIE_SECURE, httponly=True, samesite=settings.COOKIE_SAMESITE)
    response.delete_cookie(GOOGLE_COOKIE, domain=settings.COOKIE_DOMAIN, path="/api/auth",
        secure=settings.COOKIE_SECURE, httponly=True, samesite=settings.COOKIE_SAMESITE)
    return {"ok": True}


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {"user": public_user(user)}
