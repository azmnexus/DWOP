"""User repository for authentication, identity lookups, and RBAC queries."""
from __future__ import annotations

import uuid
from typing import List, NamedTuple, Optional
from sqlalchemy.orm import Session, load_only

from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.repositories.base import BaseRepository


class PrincipalGuard(NamedTuple):
    """Result of the single hybrid offboarding-guard query (ADR-002 Phase 3).

    ``user`` is fully hydrated so downstream services reuse the identity-map
    instance without issuing another query. ``tenant_is_active`` carries the
    workspace lifecycle flag from the same round-trip.
    """

    user: Optional[User]
    tenant_is_active: Optional[bool]


class UserRepository(BaseRepository[User]):
    """Domain repository for User identities and credentials."""

    def __init__(self, db: Session):
        super().__init__(db, User)

    def get_by_email(self, tenant_id: uuid.UUID, email: str) -> Optional[User]:
        """Fetch user by email strictly scoped to tenant."""
        return (
            self._scoped_query(tenant_id)
            .filter(User.email == email.strip().lower())
            .first()
        )

    def get_by_email_global(self, email: str) -> Optional[User]:
        """Lookup user across tenants by unique email (used during authentication challenge)."""
        return (
            self.db.query(User)
            .filter(User.email == email.strip().lower())
            .first()
        )

    def get_by_id_global(self, user_id: uuid.UUID) -> Optional[User]:
        """Fetch user by id across tenants (used during JWT payload validation)."""
        return self.db.query(User).filter(User.id == user_id).first()

    def get_lifecycle_flags(self, user_id: uuid.UUID) -> PrincipalGuard:
        """Single query returning the user plus both lifecycle flags.

        This is the *only* database round-trip DWOP performs per authenticated
        request for authorization purposes. It exists solely to support instant
        revocation of offboarded professionals (``User.is_active``) and
        suspended workspaces (``Tenant.is_active``). All RBAC permission
        computing stays in the in-memory
        :class:`~app.core.policy.PolicyEngine`.

        The projection is deliberately narrow: every column the request
        pipeline can legally read is listed in ``load_only``, and the bcrypt
        ``hashed_password`` is never fetched on an authenticated request.
        """
        row = (
            self.db.query(User, Tenant.is_active.label("tenant_is_active"))
            .join(Tenant, Tenant.id == User.tenant_id)
            .options(
                load_only(
                    User.id,
                    User.tenant_id,
                    User.email,
                    User.role,
                    User.is_active,
                    User.created_at,
                )
            )
            .filter(User.id == user_id)
            .first()
        )
        if row is None:
            return PrincipalGuard(user=None, tenant_is_active=None)
        return PrincipalGuard(user=row[0], tenant_is_active=bool(row[1]))

    def list_by_role(self, tenant_id: uuid.UUID, role: UserRole) -> List[User]:
        """List active users within a tenant matching the given role."""
        return (
            self._scoped_query(tenant_id)
            .filter(User.role == role, User.is_active == True)
            .all()
        )
