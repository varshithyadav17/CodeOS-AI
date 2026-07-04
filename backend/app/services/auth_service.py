"""Auth service — pure business logic, depends on interfaces only."""
from __future__ import annotations
from fastapi import HTTPException, status

from ..core.models.user import User
from ..core.interfaces.metadata import IMetadataRepository
from ..core.security import hash_password, verify_password, create_token


class AuthService:
    def __init__(self, users: IMetadataRepository[User]):
        self.users = users

    async def signup(self, email: str, password: str, name: str) -> tuple[str, User]:
        existing = await self.users.find_one({"email": email.lower()})
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")
        user = User(
            email=email.lower(),
            name=name,
            password_hash=hash_password(password),
            provider="local",
        )
        await self.users.insert(user)
        return create_token(user.id, user.email), user

    async def login(self, email: str, password: str) -> tuple[str, User]:
        user = await self.users.find_one({"email": email.lower()})
        if not user or not user.password_hash or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return create_token(user.id, user.email), user

    async def upsert_google_user(self, email: str, name: str, picture: str | None) -> tuple[str, User]:
        existing = await self.users.find_one({"email": email.lower()})
        if existing:
            return create_token(existing.id, existing.email), existing
        user = User(email=email.lower(), name=name, picture=picture, provider="google")
        await self.users.insert(user)
        return create_token(user.id, user.email), user

    async def get_by_id(self, user_id: str) -> User | None:
        return await self.users.get(user_id)
