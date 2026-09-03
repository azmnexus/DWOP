from fastapi import APIRouter
from app.api.auth import router as auth_router
from app.api.tenants import router as tenants_router
from app.api.departments import router as departments_router
from app.api.teams import router as teams_router
from app.api.clients import router as clients_router
from app.api.people import router as people_router
from app.api.onboarding import router as onboarding_router
from app.api.assignments import router as assignments_router
from app.api.access import router as access_router
from app.api.audit import router as audit_router
from app.api.integrations import router as integrations_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(tenants_router)
api_router.include_router(departments_router)
api_router.include_router(teams_router)
api_router.include_router(clients_router)
api_router.include_router(people_router)
api_router.include_router(onboarding_router)
api_router.include_router(assignments_router)
api_router.include_router(access_router)
api_router.include_router(audit_router)
api_router.include_router(integrations_router)
