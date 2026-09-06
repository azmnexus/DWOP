from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import create_access_token, create_refresh_token, verify_password
from backend.models.user import User


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate(self, email: str, password: str) -> tuple[User, str, str]:
        # Global email lookup (multi-tenant login without tenant hint)
        result = await self.db.execute(select(User).where(User.email == email))
        users = result.scalars().all()
        user = None
        for u in users:
            if verify_password(password, u.hashed_password):
                user = u
                break
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")
        access = create_access_token(subject=user.id, tenant_id=user.tenant_id, role=user.role.value if hasattr(user.role, "value") else str(user.role), email=user.email)
        refresh = create_refresh_token(subject=user.id, tenant_id=user.tenant_id)
        return user, access, refresh
