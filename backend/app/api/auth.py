import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import (
    get_current_active_user,
    get_current_policy_subject,
)
from app.core.policy import PolicySubject, policy_engine
from app.core.security import verify_password, create_access_token
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserRead
from app.services.audit import AuditService

router = APIRouter(prefix="/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str
    email: str
    # ADR-002: fully expanded, in-memory-resolved permission set for this role.
    permissions: List[str] = Field(default_factory=list)


class PolicyResponse(BaseModel):
    """Effective authorization policy resolved in application memory."""

    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str
    permissions: List[str]
    tenant_boundary_enforced: bool = True
    rbac_mode: str = "stateless-in-memory-policy-matrix"


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    db: Session = Depends(get_db),
):
    """Authenticate user with email and password against database.
    Supports both JSON payload and OAuth2 Form (for Swagger UI Authorize button).
    """
    content_type = request.headers.get("content-type", "")
    email: Optional[str] = None
    password: Optional[str] = None

    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        email = form.get("username") or form.get("email")
        password = form.get("password")
    else:
        try:
            body = await request.json()
            email = body.get("email")
            password = body.get("password")
        except Exception:
            pass

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both 'email' and 'password' are required.",
        )

    # Lookup user by email in database via UserRepository
    user = UserRepository(db).get_by_email_global(str(email))
    if not user or not verify_password(str(password), user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive. Please contact your administrator.",
        )

    # ADR-002: refuse to mint tokens into a suspended workspace. The same flag is
    # re-verified by the per-request offboarding guard.
    if not user.tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant workspace is suspended. Please contact your administrator.",
        )

    role_value = user.role.value if hasattr(user.role, "value") else str(user.role)
    # Expanded once, in memory, from the policy matrix.
    permissions = policy_engine.permissions_for_token(role_value)

    # Issue JWT embedding the signed role, tenant_id, and permissions claims
    access_token = create_access_token(
        subject=str(user.id),
        tenant_id=str(user.tenant_id),
        role=role_value,
        email=user.email,
        permissions=permissions,
    )

    # Log immutable audit event for successful authentication
    AuditService(db).log_event(
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        action="auth.login_successful",
        target_type="User",
        target_id=user.id,
        metadata={"email": user.email, "role": role_value, "permission_count": len(permissions)},
        commit=True,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=role_value,
        email=user.email,
        permissions=permissions,
    )


@router.get("/me", response_model=UserRead)
def get_current_user_profile(
    current_user: User = Depends(get_current_active_user),
):
    """Retrieve profile and role of the currently authenticated user."""
    return current_user


@router.get("/policy", response_model=PolicyResponse)
def get_effective_policy(
    current_user: User = Depends(get_current_active_user),
    subject: PolicySubject = Depends(get_current_policy_subject),
):
    """Return the caller's effective policy, resolved entirely in application memory.

    No database or cache lookup is involved in computing ``permissions``: they are
    derived from the signature-verified ``role`` claim via the in-memory policy
    matrix. Clients use this to drive RBAC-aware navigation without duplicating
    authorization logic.
    """
    return PolicyResponse(
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        role=subject.role or "",
        permissions=list(policy_engine.permissions_for_role(subject.role)),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_access_token(
    current_user: User = Depends(get_current_active_user),
    subject: PolicySubject = Depends(get_current_policy_subject),
):
    """Re-issue an access token with freshly expanded role/permission claims."""
    role_value = subject.role or (
        current_user.role.value
        if hasattr(current_user.role, "value")
        else str(current_user.role)
    )
    permissions = policy_engine.permissions_for_token(role_value)
    access_token = create_access_token(
        subject=str(current_user.id),
        tenant_id=str(current_user.tenant_id),
        role=role_value,
        email=current_user.email,
        permissions=permissions,
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        role=role_value,
        email=current_user.email,
        permissions=permissions,
    )


@router.post("/logout")
def logout(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Log out current user and record audit logout event."""
    AuditService(db).log_event(
        tenant_id=current_user.tenant_id,
        actor_user_id=current_user.id,
        action="auth.logout",
        target_type="User",
        target_id=current_user.id,
        metadata={"email": current_user.email},
        commit=True,
    )
    return {"status": "logged_out", "detail": "Session successfully invalidated."}
