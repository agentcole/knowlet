import uuid
from pydantic import BaseModel, EmailStr


class TenantCreate(BaseModel):
    name: str


class TenantUpdate(BaseModel):
    name: str | None = None
    settings: dict | None = None


class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    settings: dict | None

    model_config = {"from_attributes": True}


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: str = "member"


class MemberResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str
    role: str
