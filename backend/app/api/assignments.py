import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_db,
    get_assignment_service,
    get_project_repository,
    get_professional_repository,
    get_current_active_user,
    require_admin,
    require_admin_or_manager,
)
from app.models.user import User
from app.models.project import Project, ProjectStatus, Client
from app.models.assignment import Assignment, AssignmentStatus
from app.repositories.project import ProjectRepository
from app.repositories.professional import ProfessionalRepository
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectRead,
)
from app.schemas.assignment import (
    AssignmentCreate,
    AssignmentUpdate,
    AssignmentRead,
    CapacityOverviewRead,
    ProfessionalCapacityRead,
)
from app.services.assignment import AssignmentService

router = APIRouter(prefix="/assignments", tags=["Assignments & Capacity Engine"])


# ---------------- Project Management Endpoints ----------------
@router.get("/projects", response_model=List[ProjectRead])
def list_projects(
    status: Optional[ProjectStatus] = None,
    client_id: Optional[uuid.UUID] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    project_repo: ProjectRepository = Depends(get_project_repository),
):
    """List projects scoped to tenant with optional client and status filters."""
    return project_repo.list_projects(
        tenant_id=current_user.tenant_id,
        client_id=client_id,
        status=status,
        skip=skip,
        limit=limit,
    )


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    admin_user: User = Depends(require_admin),
    project_repo: ProjectRepository = Depends(get_project_repository),
    db: Session = Depends(get_db),
):
    """Create a new project (Requires ADMIN role)."""
    if payload.client_id:
        client = project_repo.get_client(admin_user.tenant_id, payload.client_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Client '{payload.client_id}' not found in current tenant.",
            )

    # Check for duplicate project code within the tenant
    existing = project_repo.get_by_code(admin_user.tenant_id, payload.code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project with code '{payload.code}' already exists in this tenant.",
        )

    project = Project(
        tenant_id=admin_user.tenant_id,
        client_id=payload.client_id,
        name=payload.name,
        code=payload.code.strip().upper(),
        status=payload.status,
        start_date=payload.start_date,
        target_end_date=payload.target_end_date,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    project_repo: ProjectRepository = Depends(get_project_repository),
):
    """Retrieve details for a project in current tenant (Accessible by all members)."""
    project = project_repo.get_by_id(current_user.tenant_id, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found in current tenant.",
        )
    return project


@router.put("/projects/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    admin_user: User = Depends(require_admin),
    project_repo: ProjectRepository = Depends(get_project_repository),
    db: Session = Depends(get_db),
):
    """Update project details (Requires ADMIN role)."""
    project = project_repo.get_by_id(admin_user.tenant_id, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found in current tenant.",
        )

    if payload.client_id:
        client = project_repo.get_client(admin_user.tenant_id, payload.client_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Client '{payload.client_id}' not found in current tenant.",
            )

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: uuid.UUID,
    admin_user: User = Depends(require_admin),
    project_repo: ProjectRepository = Depends(get_project_repository),
    db: Session = Depends(get_db),
):
    """Delete a project (Requires ADMIN role)."""
    project = project_repo.get_by_id(admin_user.tenant_id, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found in current tenant.",
        )
    db.delete(project)
    db.commit()
    return None


# ---------------- Capacity & Allocation Endpoints ----------------
@router.get("/capacity", response_model=CapacityOverviewRead)
def get_capacity_overview(
    current_user: User = Depends(get_current_active_user),
    service: AssignmentService = Depends(get_assignment_service),
):
    """Query aggregate platform capacity allocations and availability (Accessible by all members)."""
    return service.get_capacity_overview(current_user.tenant_id)


@router.get("/capacity/professionals/{professional_id}", response_model=ProfessionalCapacityRead)
def get_professional_capacity(
    professional_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    service: AssignmentService = Depends(get_assignment_service),
):
    """Retrieve detailed capacity allocations and utilization for a specific professional."""
    return service.get_professional_capacity(current_user.tenant_id, professional_id)


@router.post("/allocate", response_model=AssignmentRead, status_code=status.HTTP_201_CREATED)
def allocate_capacity(
    payload: AssignmentCreate,
    operator: User = Depends(require_admin_or_manager),
    service: AssignmentService = Depends(get_assignment_service),
):
    """Allocate a professional to a project.
    Enforces the 100% capacity limit ceiling and logs an immutable audit event.
    Requires ADMIN or MANAGER role.
    """
    return service.allocate_capacity(operator.tenant_id, payload, operator)


@router.get("", response_model=List[AssignmentRead])
def list_assignments(
    project_id: Optional[uuid.UUID] = None,
    professional_id: Optional[uuid.UUID] = None,
    status: Optional[AssignmentStatus] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    service: AssignmentService = Depends(get_assignment_service),
):
    """List project assignments scoped to current tenant with optional filters."""
    return service.list_assignments(
        tenant_id=current_user.tenant_id,
        project_id=project_id,
        professional_id=professional_id,
        status_filter=status,
        skip=skip,
        limit=limit,
    )


@router.get("/", response_model=List[AssignmentRead], include_in_schema=False)
def list_assignments_slash(
    project_id: Optional[uuid.UUID] = None,
    professional_id: Optional[uuid.UUID] = None,
    status: Optional[AssignmentStatus] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    service: AssignmentService = Depends(get_assignment_service),
):
    """Trailing-slash compatibility alias."""
    return service.list_assignments(
        tenant_id=current_user.tenant_id,
        project_id=project_id,
        professional_id=professional_id,
        status_filter=status,
        skip=skip,
        limit=limit,
    )


@router.get("/my-allocations", response_model=List[AssignmentRead])
def get_my_allocations(
    current_user: User = Depends(get_current_active_user),
    prof_repo: ProfessionalRepository = Depends(get_professional_repository),
    service: AssignmentService = Depends(get_assignment_service),
):
    """Retrieve active project allocations for the authenticated professional."""
    prof = prof_repo.get_by_user_id(current_user.tenant_id, current_user.id)
    if not prof:
        return []
    return service.list_assignments(
        tenant_id=current_user.tenant_id,
        professional_id=prof.id,
    )


@router.get("/{assignment_id}", response_model=AssignmentRead)
def get_assignment(
    assignment_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    service: AssignmentService = Depends(get_assignment_service),
):
    """Retrieve details for a single assignment by ID."""
    assignment = service.assignment_repo.get_by_id(current_user.tenant_id, assignment_id)
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment '{assignment_id}' not found in current tenant.",
        )
    return service._enrich_assignment(assignment)


@router.patch("/{assignment_id}", response_model=AssignmentRead)
def update_assignment(
    assignment_id: uuid.UUID,
    payload: AssignmentUpdate,
    operator: User = Depends(require_admin_or_manager),
    service: AssignmentService = Depends(get_assignment_service),
):
    """Update an assignment's capacity percentage, status, or role.
    Enforces maximum 100% capacity rule and logs immutable audit trail.
    Requires ADMIN or MANAGER role.
    """
    return service.update_assignment(
        tenant_id=operator.tenant_id,
        assignment_id=assignment_id,
        payload=payload,
        actor=operator,
    )


@router.put("/{assignment_id}", response_model=AssignmentRead, include_in_schema=False)
def update_assignment_put(
    assignment_id: uuid.UUID,
    payload: AssignmentUpdate,
    operator: User = Depends(require_admin_or_manager),
    service: AssignmentService = Depends(get_assignment_service),
):
    """PUT compatibility alias for updating an assignment."""
    return service.update_assignment(
        tenant_id=operator.tenant_id,
        assignment_id=assignment_id,
        payload=payload,
        actor=operator,
    )
