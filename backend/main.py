from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import get_settings
from backend.core.middleware import TenantContextMiddleware
from backend.api import api_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="DWOP - Digital Workforce Operations Platform (Multi-tenant)",
)

# Middleware: tenant context must run early
app.add_middleware(TenantContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "env": settings.app_env}

@app.get("/", tags=["health"])
async def root():
    return {"message": "DWOP API running", "docs": "/docs"}
