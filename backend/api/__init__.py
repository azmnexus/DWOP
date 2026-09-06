from fastapi import APIRouter
from backend.api import auth, tenants, users, departments, teams, clients, projects

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(tenants.router)
api_router.include_router(users.router)
api_router.include_router(departments.router)
api_router.include_router(teams.router)
api_router.include_router(clients.router)
api_router.include_router(projects.router)
