from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.core.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---- Password hashing ----
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ---- JWT (OIDC-compatible) ----
def create_access_token(
    *,
    subject: str | uuid.UUID,
    tenant_id: str | uuid.UUID,
    role: str,
    email: Optional[str] = None,
    extra_claims: Optional[dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create OIDC-compatible JWT.
    Claims:
        sub: user id
        tenant_id / tid: tenant scope (both for compatibility)
        role: RBAC role
        email: user email
        iss: issuer
        aud: audience
        exp, iat
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "tenant_id": str(tenant_id),
        "tid": str(tenant_id),  # OIDC alias
        "role": role,
        "iss": settings.oidc_issuer,
        "aud": settings.oidc_audience,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    if email:
        to_encode["email"] = email
    if extra_claims:
        to_encode.update(extra_claims)
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
            options={"verify_aud": True, "verify_iss": True},
        )
        return payload
    except JWTError as e:
        # Fallback without aud/iss verification for dev flexibility - try again lenient
        try:
            payload = jwt.decode(
                token,
                settings.secret_key,
                algorithms=[settings.algorithm],
                options={"verify_aud": False, "verify_iss": False},
            )
            return payload
        except JWTError:
            raise e


def create_refresh_token(subject: str | uuid.UUID, tenant_id: str | uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    to_encode = {
        "sub": str(subject),
        "tenant_id": str(tenant_id),
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
