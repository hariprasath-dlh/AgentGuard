"""Auth API router: register, login, me, API key management."""
import logging
import traceback
import uuid
from datetime import UTC, datetime
from typing import List

_log = logging.getLogger(__name__)

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
    OAuthExchangeRequest,
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


from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.services.oauth import (
    consume_oauth_exchange_code,
    exchange_google_code,
    generate_oauth_state,
    get_google_auth_url,
    store_oauth_exchange_code,
    validate_oauth_state,
    verify_google_id_token,
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(request: UserRegisterRequest, db: Session = Depends(get_db)):
    """Register a new user.

    Email is globally unique. Organization creation logic:
    - If `organization_slug` is provided and the org exists → join that org.
    - If `organization_slug` is provided and the org does NOT exist → create org + make this user ADMIN.
    - If no `organization_slug` is provided → generate slug from email domain + uuid4 suffix,
      create a new org, and make this user ADMIN.
    """
    # Check for duplicate email globally across the entire platform
    existing_user = get_user_by_email(db, request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

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
        organization_name=org.name,
        organization_slug=org.slug,
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
    user = get_user_by_email(db, request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is registered via Google sign-in. Please use 'Continue with Google'.",
        )
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if request.organization_slug:
        if not user.organization or user.organization.slug != request.organization_slug:
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


# ---------------------------------------------------------------------------
# Google OAuth 2.0 Endpoints
# ---------------------------------------------------------------------------

@router.get("/google/login")
def google_login(redirect_target: str | None = None):
    """Initiate Google OAuth 2.0 Authorization Code flow with CSRF state token."""
    state = generate_oauth_state(redirect_target=redirect_target)
    auth_url = get_google_auth_url(state=state)
    return RedirectResponse(url=auth_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/google/callback")
def google_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """Handle Google OAuth 2.0 redirect callback.

    Exchanges authorization code for verified Google ID token, enforces state CSRF
    verification, resolves or auto-provisions the user identity, and issues a JWT token.
    """
    try:
        return _google_callback_impl(code=code, state=state, error=error, db=db)
    except Exception as _top_exc:
        _log.error(
            "OAUTH CALLBACK UNHANDLED EXCEPTION: %s\n%s",
            _top_exc,
            traceback.format_exc(),
        )
        frontend_url = settings.FRONTEND_URL
        return RedirectResponse(
            url=f"{frontend_url}/login?error=internal_error",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )


def _google_callback_impl(
    code: str | None,
    state: str | None,
    error: str | None,
    db: Session,
):
    """Inner implementation of the Google OAuth callback (separated for clean exception tracing)."""
    frontend_url = settings.FRONTEND_URL

    if error:
        return RedirectResponse(
            url=f"{frontend_url}/login?error={error}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    if not code or not state:
        return RedirectResponse(
            url=f"{frontend_url}/login?error=missing_oauth_parameters",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    # 1. Enforce OAuth State parameter validation (CSRF defense)
    state_payload = validate_oauth_state(state)
    if not state_payload:
        return RedirectResponse(
            url=f"{frontend_url}/login?error=invalid_or_expired_state",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    # 2. Exchange authorization code for tokens & verify ID token
    try:
        token_data = exchange_google_code(code)
        id_token_str = token_data.get("id_token")
        if not id_token_str:
            raise ValueError("Google did not return an id_token")
        id_info = verify_google_id_token(id_token_str)
    except Exception as exc:
        _log.error("OAuth token exchange/verification failed: %s\n%s", exc, traceback.format_exc())
        return RedirectResponse(
            url=f"{frontend_url}/login?error=token_verification_failed",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    email = id_info["email"].strip().lower()
    full_name = id_info.get("name")

    # 3. Account resolution using globally unique email
    try:
        user = get_user_by_email(db, email)
        if not user:
            # New Google user flow: auto-provision organization with clear name & ADMIN role
            domain = email.split("@")[-1].split(".")[0] if "@" in email else "workspace"
            org_slug = f"{domain}-{uuid.uuid4().hex[:6]}"
            org_name = f"{full_name}'s Organization" if full_name else f"{domain.capitalize()} Workspace"
            org = create_organization(db, name=org_name, slug=org_slug)
            role = get_or_create_role(db, org.id, RoleEnum.ADMIN.value)
            user = create_user(
                db,
                organization_id=org.id,
                email=email,
                full_name=full_name,
                role_id=role.id,
                hashed_password=None,
            )
            db.commit()
            db.refresh(user)
    except Exception as exc:
        db.rollback()
        _log.error("Failed to provision/retrieve OAuth user: %s\n%s", exc, traceback.format_exc())
        return RedirectResponse(
            url=f"{frontend_url}/login?error=account_provision_failed",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    if not user.is_active:
        return RedirectResponse(
            url=f"{frontend_url}/login?error=account_inactive",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    role_name = user.role.name if user.role else RoleEnum.ADMIN.value
    token_claims = {
        "sub": str(user.id),
        "organization_id": str(user.organization_id),
        "role": role_name,
    }
    access_token = create_access_token(token_claims)

    # Secure token transport: issue a short-lived single-use opaque exchange code.
    # The JWT NEVER appears in browser URL, history, server logs, or Referer headers.
    exchange_code = store_oauth_exchange_code(access_token, ttl_seconds=60)

    redirect_target = state_payload.get("redirect_target") or f"{frontend_url}/login"
    if redirect_target.rstrip("/") == frontend_url.rstrip("/"):
        redirect_target = f"{frontend_url}/login"
    separator = "&" if "?" in redirect_target else "?"
    return RedirectResponse(
        url=f"{redirect_target}{separator}code={exchange_code}",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.post("/google/exchange", response_model=TokenResponse)
def google_exchange(request: OAuthExchangeRequest):
    """Exchange a short-lived, single-use one-time OAuth code for the user's JWT access token.

    Enforces single-use consumption and eliminates JWT credential leakage in URL query parameters.
    """
    token = consume_oauth_exchange_code(request.code)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, expired, or already used exchange code",
        )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: AuthenticatedUser = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return UserResponse(
        id=current_user.id,
        organization_id=current_user.organization_id,
        organization_name=current_user.organization_name,
        organization_slug=current_user.organization_slug,
        role=current_user.role,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        created_at=datetime.now(UTC),  # placeholder; real value from DB if needed
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
        revoked_at=datetime.now(UTC),
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
