from backend.models.client import Client
from backend.services.base import TenantScopedService
from sqlalchemy.ext.asyncio import AsyncSession

class ClientService(TenantScopedService[Client]):
    def __init__(self, db: AsyncSession):
        super().__init__(Client, db)
