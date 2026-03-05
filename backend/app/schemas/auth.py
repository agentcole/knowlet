import uuid
from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    tenant_name: str
    default_language: str = "en"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    default_language: str
    is_active: bool

    model_config = {"from_attributes": True}


class UserPreferencesUpdateRequest(BaseModel):
    default_language: str


class MembershipResponse(BaseModel):
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_slug: str
    role: str


class MeResponse(BaseModel):
    user: UserResponse
    memberships: list[MembershipResponse]
