"""Auth repository: user, organization, role, and API key operations."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.api_key import APIKey
from app.models.organization import Organization
from app.models.role import Role
from app.models.user import User
from app.repositories.base import OrgScopedRepository
from app.schemas.auth import RoleEnum
from app.security.api_key import hash_api_key
from app.security.password import hash_password


def get_organization_by_slug(db: Session, slug: str) -> Optional[Organization]:
    return db.query(Organization).filter(Organization.slug == slug).first()


def get_organization_by_id(db: Session, org_id: uuid.UUID) -> Optional[Organization]:
    return db.query(Organization).filter(Organization.id == org_id).first()


def create_organization(db: Session, name: str, slug: str) -> Organization:
    org = Organization(name=name, slug=slug)
    db.add(org)
    db.flush()  # get org.id without committing
    return org


def get_or_create_role(
    db: Session, organization_id: uuid.UUID, role_name: str
) -> Role:
    role = (
        db.query(Role)
        .filter(Role.organization_id == organization_id, Role.name == role_name)
        .first()
    )
    if not role:
        role = Role(organization_id=organization_id, name=role_name)
        db.add(role)
        db.flush()
    return role


def get_user_by_email(db: Session, email: str, organization_id: uuid.UUID) -> Optional[User]:
    return (
        db.query(User)
        .filter(User.email == email, User.organization_id == organization_id)
        .first()
    )


def get_user_by_id(db: Session, user_id: uuid.UUID) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def create_user(
    db: Session,
    *,
    organization_id: uuid.UUID,
    email: str,
    password: str,
    full_name: Optional[str] = None,
    role_id: Optional[uuid.UUID] = None,
) -> User:
    user = User(
        organization_id=organization_id,
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role_id=role_id,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


# ---------------------------------------------------------------------------
# API key operations (org-scoped)
# ---------------------------------------------------------------------------

class APIKeyRepository(OrgScopedRepository):
    def get_active_by_hash(self, key_hash: str) -> Optional[APIKey]:
        return (
            self._base_query(APIKey)
            .filter(APIKey.key_hash == key_hash, APIKey.is_active == True)
            .first()
        )

    def create(
        self,
        *,
        name: str,
        raw_key: str,
        key_prefix: str,
        agent_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
        expires_at: Optional[datetime] = None,
    ) -> APIKey:
        key = APIKey(
            organization_id=self.organization_id,
            name=name,
            key_hash=hash_api_key(raw_key),
            key_prefix=key_prefix,
            agent_id=agent_id,
            user_id=user_id,
            expires_at=expires_at,
            is_active=True,
        )
        self.db.add(key)
        self.db.flush()
        return key

    def revoke(self, key_id: uuid.UUID) -> Optional[APIKey]:
        key = self.get_by_id(APIKey, key_id)
        if key:
            key.is_active = False
            self.db.flush()
        return key

    def list_active(self) -> list[APIKey]:
        return self._base_query(APIKey).filter(APIKey.is_active == True).all()
