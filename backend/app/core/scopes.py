"""Derived-scope resolution for situational RBAC authority (Task O-02, Phase 2).

This module is the *only* place where relational data is converted into
authorization input. It answers one question: which derived scopes does this
user currently hold, and which resources are they bound to?

Currently one scope is derived:

``team_lead``
    Emitted when the user is referenced by ``Team.team_lead_id`` for at least one
    team. The bound resource set is the set of team IDs they lead.

Design constraints held here deliberately:

* **No fourth global role.** ``Team Lead`` is not a member of
  :class:`~app.models.user.UserRole`, is not persisted in ``users.role``, and
  requires no schema change. Removing a team lead is a single ``team_lead_id``
  update, not a migration.
* **Derived, never granted.** Authority cannot be self-asserted; it exists only
  because a row points at the user. There is no request path that writes
  ``users.role`` to express it.
* **Narrower than role.** Scope permissions are always resource-bound in
  :mod:`app.core.policy`; a scope can never widen the tenant boundary.

Derivation runs at token issuance (login and refresh), which already performs
database work, so the per-request authorization path stays at its single
offboarding-guard query.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import FrozenSet, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.organization import Team
from app.core.policy import Scope

__all__ = ["ScopeGrant", "ScopeResolver", "EMPTY_SCOPE_GRANT", "resolve_scope_grant"]


@dataclass(frozen=True)
class ScopeGrant:
    """The derived scopes a principal holds and the resources binding them."""

    scopes: FrozenSet[str] = frozenset()
    lead_team_ids: Tuple[uuid.UUID, ...] = ()

    @property
    def is_team_lead(self) -> bool:
        return Scope.TEAM_LEAD in self.scopes

    @property
    def lead_teams(self) -> list[str]:
        return [str(team_id) for team_id in self.lead_team_ids]

    def to_claims(self) -> dict:
        """Claims fragment to embed in the access JWT."""
        return {
            "scopes": sorted(self.scopes),
            "lead_teams": self.lead_teams,
        }


EMPTY_SCOPE_GRANT = ScopeGrant()


class ScopeResolver:
    """Derives in-memory scopes from relational data."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_led_team_ids(self, user_id: uuid.UUID) -> Tuple[uuid.UUID, ...]:
        """Team IDs whose ``team_lead_id`` points at this user."""
        rows = self.db.execute(
            select(Team.id).where(Team.team_lead_id == user_id)
        ).scalars()
        return tuple(row for row in rows if row is not None)

    def derive(self, user_id: uuid.UUID) -> ScopeGrant:
        """Resolve every derived scope currently held by ``user_id``."""
        if user_id is None:
            return EMPTY_SCOPE_GRANT

        led_teams = self.list_led_team_ids(user_id)
        scopes: set[str] = set()
        if led_teams:
            # Team Lead authority exists only as long as Team.team_lead_id says so.
            scopes.add(Scope.TEAM_LEAD)
        return ScopeGrant(scopes=frozenset(scopes), lead_team_ids=led_teams)


def resolve_scope_grant(db: Session, user_id: uuid.UUID) -> ScopeGrant:
    """Convenience wrapper around :class:`ScopeResolver`."""
    return ScopeResolver(db).derive(user_id)


def lead_team_ids_as_sequence(
    grant: ScopeGrant,
) -> Sequence[uuid.UUID]:
    """Bound resource identifiers for the grant, as a plain sequence."""
    return grant.lead_team_ids