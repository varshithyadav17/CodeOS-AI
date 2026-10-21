"""JWT validation and bounded scrypt password hashing (bcrypt legacy verification)."""
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import secrets
import jwt
from .config import settings


def hash_password(password):
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(key).decode()


def verify_password(password, password_hash):
    try:
        if password_hash.startswith("scrypt$"):
            _, salt, expected = password_hash.split("$")
            actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=16384, r=8, p=1, dklen=32)
            return hmac.compare_digest(actual, base64.b64decode(expected))
        import bcrypt
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except (ValueError, TypeError):
        return False


def create_token(user_id, email):
    return jwt.encode({"sub": user_id, "email": email, "iss": "codeos-ai", "aud": "codeos-api",
        "iat": datetime.now(timezone.utc), "exp": datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRY_HOURS)},
        settings.JWT_SECRET, algorithm="HS256")


def decode_token(token):
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"], audience="codeos-api", issuer="codeos-ai",
        options={"require": ["sub", "exp", "iat", "iss", "aud"]})



def encrypt_credential(value):
    from cryptography.fernet import Fernet
    key=base64.urlsafe_b64encode(hashlib.sha256(("codeos-github:"+settings.JWT_SECRET).encode()).digest())
    return Fernet(key).encrypt(value.encode()).decode()


def decrypt_credential(value):
    from cryptography.fernet import Fernet, InvalidToken
    key=base64.urlsafe_b64encode(hashlib.sha256(("codeos-github:"+settings.JWT_SECRET).encode()).digest())
    try:
        return Fernet(key).decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("GitHub credential is unavailable. Re-import using a new access token.") from exc
