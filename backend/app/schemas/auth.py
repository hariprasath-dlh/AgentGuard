import re
import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RoleEnum(str, Enum):
    ADMIN = "ADMIN"
    SECURITY = "SECURITY"
    AUDITOR = "AUDITOR"
    MANAGER = "MANAGER"
    DEVELOPER = "DEVELOPER"


class UserRegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=72)
    full_name: str | None = Field(None, max_length=255)
    organization_name: str | None = Field(None, min_length=2, max_length=255)
    organization_slug: str | None = Field(None, min_length=2, max_length=255)
    role: RoleEnum | None = None

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format")
        return v


class UserLoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1)
    organization_slug: str | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class OAuthExchangeRequest(BaseModel):
    code: str = Field(..., min_length=1, description="One-time opaque OAuth exchange code")  # in seconds


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    organization_name: str | None = None
    organization_slug: str | None = None
    role_id: uuid.UUID | None = None
    role: str | None = None
    email: str
    full_name: str | None = None
    is_active: bool
    created_at: datetime


class APIKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    agent_id: uuid.UUID | None = None
    expires_at: datetime | None = None


class APIKeyCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    key_prefix: str
    api_key: str
    agent_id: uuid.UUID | None = None
    organization_id: uuid.UUID
    created_at: datetime


class APIKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    key_prefix: str
    agent_id: uuid.UUID | None = None
    organization_id: uuid.UUID
    is_active: bool
    created_at: datetime
    expires_at: datetime | None = None


class APIKeyRevokeResponse(BaseModel):
    id: uuid.UUID
    is_active: bool
    revoked_at: datetime
