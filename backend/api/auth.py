from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.user import TokenResponse, UserLogin, UserRead
from backend.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """OAuth2 password flow - tenant_id resolved from user record -> embedded in JWT."""
    svc = AuthService(db)
    user, access, refresh = await svc.authenticate(form.username, form.password)
    return TokenResponse(access_token=access, refresh_token=refresh, tenant_id=user.tenant_id, role=user.role)

@router.post("/login/json", response_model=TokenResponse)
async def login_json(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    svc = AuthService(db)
    user, access, refresh = await svc.authenticate(payload.email, payload.password)
    return TokenResponse(access_token=access, refresh_token=refresh, tenant_id=user.tenant_id, role=user.role)

@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
