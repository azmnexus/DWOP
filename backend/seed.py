"""
Seed script for local dev: creates one tenant + admin user.
Run: python -m backend.seed
"""
import asyncio
import uuid
from sqlalchemy import select
from backend.core.database import AsyncSessionLocal
from backend.models.tenant import Tenant
from backend.models.user import User, UserRole
from backend.core.security import get_password_hash

async def seed():
    async with AsyncSessionLocal() as db:
        # Tenant
        result = await db.execute(select(Tenant).where(Tenant.slug == "acme"))
        tenant = result.scalar_one_or_none()
        if not tenant:
            tenant = Tenant(name="Acme Corp", slug="acme", domain="acme.local", plan_tier="pro", branding={"primary_color": "#0ea5e9"})
            db.add(tenant)
            await db.flush()
            print(f"Created tenant {tenant.id}")
        else:
            print(f"Tenant exists {tenant.id}")

        result = await db.execute(select(User).where(User.tenant_id == tenant.id, User.email == "admin@acme.local"))
        user = result.scalar_one_or_none()
        if not user:
            user = User(tenant_id=tenant.id, email="admin@acme.local", hashed_password=get_password_hash("Admin123!"), role=UserRole.ADMIN, is_active=True)
            db.add(user)
            await db.flush()
            print(f"Created admin {user.email} / Admin123!")
        else:
            print(f"Admin exists {user.email}")
        await db.commit()

if __name__ == "__main__":
    asyncio.run(seed())
