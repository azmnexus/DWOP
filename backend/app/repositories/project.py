"""Project repository for commercial delivery projects and client portfolios."""
from __future__ import annotations

import uuid
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.project import Client, ClientStatus, Project, ProjectStatus
from app.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    """Domain repository managing commercial clients and delivery projects."""

    def __init__(self, db: Session):
        super().__init__(db, Project)
        self.client_repo = BaseRepository[Client](db, Client)

    # ---------------- Project Operations ----------------
    def get_by_code(self, tenant_id: uuid.UUID, code: str) -> Optional[Project]:
        """Fetch project by delivery code strictly scoped to tenant."""
        return (
            self._scoped_query(tenant_id)
            .filter(Project.code == code.strip().upper())
            .first()
        )

    def list_projects(
        self,
        tenant_id: uuid.UUID,
        client_id: Optional[uuid.UUID] = None,
        status: Optional[ProjectStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Project]:
        """Retrieve paginated projects within tenant, with optional client/status filters."""
        query = self._scoped_query(tenant_id)
        if client_id:
            query = query.filter(Project.client_id == client_id)
        if status:
            query = query.filter(Project.status == status)
        return query.offset(skip).limit(limit).all()

    # ---------------- Client Operations ----------------
    def get_client(
        self, tenant_id: uuid.UUID, client_id: uuid.UUID
    ) -> Optional[Client]:
        """Fetch client by id strictly scoped to tenant."""
        return self.client_repo.get_by_id(tenant_id, client_id)

    def get_client_by_name(
        self, tenant_id: uuid.UUID, name: str
    ) -> Optional[Client]:
        """Fetch client by company name strictly scoped to tenant."""
        return (
            self.client_repo._scoped_query(tenant_id)
            .filter(Client.name == name.strip())
            .first()
        )

    def list_clients(
        self,
        tenant_id: uuid.UUID,
        status: Optional[ClientStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Client]:
        """List commercial clients for tenant."""
        query = self.client_repo._scoped_query(tenant_id)
        if status:
            query = query.filter(Client.status == status)
        return query.offset(skip).limit(limit).all()

    def create_client(self, client: Client) -> Client:
        """Stage client creation without committing."""
        self.db.add(client)
        self.db.flush()
        return client
