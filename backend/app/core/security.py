"""Password hashing and JWT issuance for DWOP (ADR-002: Stateless RBAC).

The access token is the authorization substrate. It is cryptographically signed
with ``SECRET_KEY`` and embeds the claims the in-memory
:class:`~app.core.policy.PolicyEngine` needs to resolve permissions without a
database lookup:

* ``role``       - the user's verified role, resolved server-side at login.
* ``tenant_id``  - the tenant boundary the token is bound to.
* ``perms``      - the fully expanded permission set for that role.
* ``scopes``     - derived scopes (e.g. ``team_lead``) computed from
  ``Team.team_lead_id``, never from a stored role.
* ``lead_teams`` - the resources the derived scopes are bound to.

Because the payload is signed, an attacker cannot widen their own authority by
editing a claim: tampering invalidates the signature and
:func:`decode_access_token` rejects the token outright.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Union

import bcrypt
from jose import jwt, JWTError

from app.core.config import settings
from app.core.policy import policy_engine

#: Claim carrying the fully expanded permission list (see Permission catalogue).
PERMISSIONS_CLAIM = "perms"
#: Claim carrying the derived, non-role scope names.
SCOPES_CLAIM = "scopes"
#: Claim carrying the resources the derived scopes are bound to.
LEAD_TEAMS_CLAIM = "lead_teams"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against the bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8")[:72],
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def resolve_permissions(
    role: Optional[str],
    permissions: Optional[Sequence[str]] = None,
) -> List[str]:
    """Resolve the permission list to embed in the token.

    The in-memory policy matrix is authoritative. ``permissions`` may be supplied
    by the caller for forward compatibility with custom roles that are not (or
    not yet) present in the matrix; for built-in roles the matrix always wins so
    a token can never carry a stale or inflated permission set.
    """
    role_value = getattr(role, "value", role)
    matrix_permissions = policy_engine.permissions_for_token(role_value)
    if role_value and policy_engine.permissions_for_role(role_value):
        return list(matrix_permissions)
    if permissions:
        return sorted({str(perm) for perm in permissions})
    return list(matrix_permissions)


def create_access_token(
    subject: Union[str, Any],
    tenant_id: Optional[str] = None,
    role: Optional[str] = None,
    email: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
    permissions: Optional[Sequence[str]] = None,
    scopes: Optional[Sequence[str]] = None,
    lead_teams: Optional[Sequence[Any]] = None,
) -> str:
    """Create a signed JWT access token carrying RBAC + tenant + scope claims.

    The returned token is self-contained: after the single offboarding-guard
    query, every subsequent authorization decision is resolved in memory from
    these claims.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    role_value = getattr(role, "value", role)

    to_encode: Dict[str, Any] = {
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
        "sub": str(subject),
        "tenant_id": str(tenant_id) if tenant_id else None,
        "role": str(role_value) if role_value else None,
        "email": str(email) if email else None,
        PERMISSIONS_CLAIM: resolve_permissions(role_value, permissions),
        SCOPES_CLAIM: sorted({str(scope) for scope in (scopes or [])}),
        LEAD_TEAMS_CLAIM: [str(team_id) for team_id in (lead_teams or [])],
        "iss": settings.TOKEN_ISSUER,
        "aud": settings.TOKEN_AUDIENCE,
        "typ": "access",
    }
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Verify the signature/issuer/audience of a JWT and return its claims.

    Raises :class:`jose.JWTError` for any tampered, expired or malformed token.
    Authorization must only ever run against the claims returned here.
    """
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
        issuer=settings.TOKEN_ISSUER,
        audience=settings.TOKEN_AUDIENCE,
    )


def token_claims(token: str) -> Dict[str, Any]:
    """Alias for :func:`decode_access_token` emphasising claim extraction."""
    try:
        return decode_access_token(token)
    except JWTError as e:
        raise e
