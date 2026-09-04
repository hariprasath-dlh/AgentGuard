"""Auth API router: register, login, me, API key management."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.auth import (
    APIKeyRepository,
    create_organization,
    create_user,
    get_or_create_role,
    get_organization_by_slug,
    get_user_by_email,
)
from app.schemas.auth import (
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyResponse,
    APIKeyRevokeResponse,
    RoleEnum,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.security.api_key import generate_api_key
from app.security.deps import AuthenticatedUser, get_current_user, require_role
from app.security.jwt import ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token
from app.security.password import verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(request: UserRegisterRequest, db: Session = Depends(get_db)):
    """Register a new user.

    Organization creation logic (ambiguity noted in Phase 3 report):
    - If `organization_slug` is provided and the org exists → join that org.
    - If `organization_slug` is provided and the org does NOT exist → create org + make this user ADMIN.
    - If no `organization_slug` is provided → generate slug from email domain + uuid4 suffix,
      create a new org, and make this user ADMIN.
    """
    org_slug = request.organization_slug
    org_name = request.organization_name

    if org_slug:
        org = get_organization_by_slug(db, org_slug)
        if not org:
            # Create new org with this slug
            if not org_name:
                org_name = org_slug.replace("-", " ").title()
            org = create_organization(db, name=org_name, slug=org_slug)
            is_first_user = True
        else:
            is_first_user = False
    else:
        # Auto-generate org slug from email domain
        domain = request.email.split("@")[-1].split(".")[0]
        suffix = str(uuid.uuid4())[:8]
        org_slug = f"{domain}-{suffix}"
        org_name = org_name or org_slug.replace("-", " ").title()
        org = create_organization(db, name=org_name, slug=org_slug)
        is_first_user = True

    # Check for duplicate email in this org
    existing_user = get_user_by_email(db, request.email, org.id)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered in this organization",
        )

    # Determine role
    role_name = request.role.value if request.role else (
        RoleEnum.ADMIN.value if is_first_user else RoleEnum.DEVELOPER.value
    )
    role = get_or_create_role(db, org.id, role_name)

    user = create_user(
        db,
        organization_id=org.id,
        email=request.email,
        password=request.password,
        full_name=request.full_name,
        role_id=role.id,
    )
    db.commit()
    db.refresh(user)

    return UserResponse(
        id=user.id,
        organization_id=user.organization_id,
        role_id=user.role_id,
        role=role_name,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post("/login", response_model=TokenResponse)
def login(request: UserLoginRequest, db: Session = Depends(get_db)):
    """Authenticate and return a JWT access token."""
    if request.organization_slug:
        org = get_organization_by_slug(db, request.organization_slug)
        if not org:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        org_id = org.id
    else:
        # Find any org containing this email; if multiple exist, require org_slug
        from app.models.user import User as UserModel
        users = db.query(UserModel).filter(UserModel.email == request.email).all()
        if not users:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        if len(users) > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email exists in multiple organizations; provide organization_slug",
            )
        org_id = users[0].organization_id

    user = get_user_by_email(db, request.email, org_id)
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    role_name = user.role.name if user.role else RoleEnum.DEVELOPER.value

    token_data = {
        "sub": str(user.id),
        "organization_id": str(user.organization_id),
        "role": role_name,
    }
    access_token = create_access_token(token_data)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: AuthenticatedUser = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return UserResponse(
        id=current_user.id,
        organization_id=current_user.organization_id,
        role=current_user.role,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        created_at=datetime.now(timezone.utc),  # placeholder; real value from DB if needed
    )


# ---------------------------------------------------------------------------
# API key management endpoints (require authentication)
# ---------------------------------------------------------------------------

@router.post("/api-keys", response_model=APIKeyCreateResponse, status_code=status.HTTP_201_CREATED)
def create_api_key(
    request: APIKeyCreateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Create a new API key. The raw key is shown ONCE — store it securely."""
    raw_key, key_prefix, _ = generate_api_key(prefix="ag_live")
    repo = APIKeyRepository(db=db, organization_id=current_user.organization_id)
    key_record = repo.create(
        name=request.name,
        raw_key=raw_key,
        key_prefix=key_prefix,
        agent_id=request.agent_id,
        user_id=current_user.id,
        expires_at=request.expires_at,
    )
    db.commit()
    db.refresh(key_record)

    return APIKeyCreateResponse(
        id=key_record.id,
        name=key_record.name,
        key_prefix=key_prefix,
        api_key=raw_key,
        agent_id=key_record.agent_id,
        organization_id=key_record.organization_id,
        created_at=key_record.created_at,
    )


@router.get("/api-keys", response_model=List[APIKeyResponse])
def list_api_keys(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """List all active API keys for the current organization."""
    repo = APIKeyRepository(db=db, organization_id=current_user.organization_id)
    keys = repo.list_active()
    return [
        APIKeyResponse(
            id=k.id,
            name=k.name,
            key_prefix=k.key_prefix,
            agent_id=k.agent_id,
            organization_id=k.organization_id,
            is_active=k.is_active,
            created_at=k.created_at,
            expires_at=k.expires_at,
        )
        for k in keys
    ]


@router.delete("/api-keys/{key_id}", response_model=APIKeyRevokeResponse)
def revoke_api_key(
    key_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Revoke an API key. Revoked keys are rejected immediately on next use."""
    repo = APIKeyRepository(db=db, organization_id=current_user.organization_id)
    key = repo.revoke(key_id)
    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    db.commit()
    return APIKeyRevokeResponse(
        id=key.id,
        is_active=key.is_active,
        revoked_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Role-restriction proof-of-concept routes
# These show the require_role() mechanism works. Real resource endpoints
# will wire in the full RBAC matrix as they are built in later phases.
# ---------------------------------------------------------------------------

@router.get("/admin-only", include_in_schema=False)
def admin_only_route(
    current_user: AuthenticatedUser = Depends(require_role(RoleEnum.ADMIN)),
):
    return {"message": "ADMIN access confirmed", "user": current_user.email}


@router.get("/security-or-admin", include_in_schema=False)
def security_or_admin_route(
    current_user: AuthenticatedUser = Depends(
        require_role(RoleEnum.ADMIN, RoleEnum.SECURITY)
    ),
):
    return {"message": "ADMIN or SECURITY access confirmed", "user": current_user.email}
