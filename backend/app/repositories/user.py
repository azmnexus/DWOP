"""User repository for authentication, identity lookups, and RBAC queries."""
from __future__ import annotations

import uuid
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.repositories.base import BaseRepository


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

    def list_by_role(self, tenant_id: uuid.UUID, role: UserRole) -> List[User]:
        """List active users within a tenant matching the given role."""
        return (
            self._scoped_query(tenant_id)
            .filter(User.role == role, User.is_active == True)
            .all()
        )
