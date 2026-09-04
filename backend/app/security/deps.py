import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional, Sequence
from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.api_key import APIKey
from app.models.user import User
from app.schemas.auth import RoleEnum
from app.security.api_key import hash_api_key
from app.security.jwt import decode_access_token

security_bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthenticatedUser:
    id: uuid.UUID
    organization_id: uuid.UUID
    email: str
    role: str
    is_active: bool
    full_name: Optional[str] = None


@dataclass
class AuthenticatedAgent:
    api_key_id: uuid.UUID
    organization_id: uuid.UUID
    agent_id: Optional[uuid.UUID]
    name: str


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    db: Session = Depends(get_db),
) -> AuthenticatedUser:
    """Extract and validate the JWT access token from the Authorization header.
    
    Loads the user from the database and returns an AuthenticatedUser.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_access_token(credentials.credentials)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).filter(User.id == user_uuid).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    
    role_name = user.role.name if user.role else (payload.get("role") or "DEVELOPER")

    return AuthenticatedUser(
        id=user.id,
        organization_id=user.organization_id,
        email=user.email,
        role=role_name,
        is_active=user.is_active,
        full_name=user.full_name,
    )


def require_role(*allowed_roles: RoleEnum) -> Callable:
    """Dependency factory restricting route access to specified roles."""
    allowed_role_values = {r.value if isinstance(r, RoleEnum) else str(r) for r in allowed_roles}

    def role_checker(current_user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if current_user.role not in allowed_role_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action not permitted for role '{current_user.role}'. Required: {sorted(list(allowed_role_values))}",
            )
        return current_user

    return role_checker


def get_current_agent(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    db: Session = Depends(get_db),
) -> AuthenticatedAgent:
    """Validate API key credentials for autonomous agent requests.
    
    Accepts API key from X-API-Key header or Bearer token starting with 'ag_'.
    Returns AuthenticatedAgent resolving to agent_id and organization_id.
    """
    raw_key = x_api_key
    if not raw_key and auth_credentials and auth_credentials.credentials.startswith("ag_"):
        raw_key = auth_credentials.credentials

    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required in X-API-Key header or Bearer token",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    key_hash = hash_api_key(raw_key)
    api_key_record = db.query(APIKey).filter(APIKey.key_hash == key_hash).first()

    if not api_key_record or not api_key_record.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )

    if api_key_record.expires_at:
        now = datetime.now(timezone.utc)
        expires_at = api_key_record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key has expired",
            )

    return AuthenticatedAgent(
        api_key_id=api_key_record.id,
        organization_id=api_key_record.organization_id,
        agent_id=api_key_record.agent_id,
        name=api_key_record.name,
    )
