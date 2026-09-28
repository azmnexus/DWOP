"""Base repository implementation enforcing multi-tenant isolation and standard CRUD."""
from __future__ import annotations

import uuid
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from pydantic import BaseModel
from sqlalchemy.orm import Query, Session

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    """Generic multi-tenant repository providing standard CRUD operations.

    Invariants:
    - All public read methods MUST route through ``_scoped_query(tenant_id)``.
    - Repositories stage and flush mutations; they NEVER commit transactions.
    """

    def __init__(self, db: Session, model: Type[ModelType]):
        self.db = db
        self.model = model

    def _scoped_query(self, tenant_id: uuid.UUID) -> Query:
        """Internal helper to construct a tenant-filtered base query.

        Ensures no read or mutation can accidentally bypass tenant boundary isolation.
        """
        if not hasattr(self.model, "tenant_id"):
            raise AttributeError(
                f"Model {self.model.__name__} does not have a tenant_id attribute."
            )
        return self.db.query(self.model).filter(self.model.tenant_id == tenant_id)

    def get_by_id(self, tenant_id: uuid.UUID, id: uuid.UUID) -> Optional[ModelType]:
        """Fetch a single entity strictly scoped to tenant."""
        return self._scoped_query(tenant_id).filter(self.model.id == id).first()

    def list_paginated(
        self, tenant_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        """Retrieve paginated records for the tenant."""
        return self._scoped_query(tenant_id).offset(skip).limit(limit).all()

    def create(self, tenant_id: uuid.UUID, obj_in: ModelType) -> ModelType:
        """Stage a new entity with guaranteed tenant scoping. Flushes without committing."""
        if hasattr(obj_in, "tenant_id") and getattr(obj_in, "tenant_id") is None:
            setattr(obj_in, "tenant_id", tenant_id)
        self.db.add(obj_in)
        self.db.flush()
        return obj_in

    def update(
        self,
        tenant_id: uuid.UUID,
        id: uuid.UUID,
        obj_in: Union[BaseModel, Dict[str, Any]],
    ) -> Optional[ModelType]:
        """Apply partial updates to an existing tenant entity. Flushes without committing."""
        entity = self.get_by_id(tenant_id, id)
        if not entity:
            return None

        if isinstance(obj_in, BaseModel):
            update_data = obj_in.model_dump(exclude_unset=True)
        elif isinstance(obj_in, dict):
            update_data = obj_in
        else:
            raise TypeError(f"Expected BaseModel or dict, got {type(obj_in)}")

        for field, value in update_data.items():
            if hasattr(entity, field) and field not in ("id", "tenant_id"):
                setattr(entity, field, value)

        self.db.flush()
        return entity

    def delete(self, tenant_id: uuid.UUID, id: uuid.UUID) -> bool:
        """Delete an entity scoped to tenant. Flushes without committing."""
        entity = self.get_by_id(tenant_id, id)
        if not entity:
            return False
        self.db.delete(entity)
        self.db.flush()
        return True

    def count(self, tenant_id: uuid.UUID) -> int:
        """Count total matching records for tenant."""
        return self._scoped_query(tenant_id).count()

    def exists(self, tenant_id: uuid.UUID, id: uuid.UUID) -> bool:
        """Check whether an entity exists in tenant."""
        return self._scoped_query(tenant_id).filter(self.model.id == id).first() is not None
