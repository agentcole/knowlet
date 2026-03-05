import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_tenant_id, get_tenant_membership
from app.models.tenant_membership import TenantMembership
from app.models.user import User
from app.schemas.tenant import (
    InviteMemberRequest,
    MemberResponse,
    TenantResponse,
    TenantUpdate,
    UpdateMemberRoleRequest,
)
from app.services import tenant_service

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])


@router.get("/current", response_model=TenantResponse)
async def get_current_tenant(
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    tenant = await tenant_service.get_tenant(db, tenant_id)
    return TenantResponse.model_validate(tenant)


@router.put("/current", response_model=TenantResponse)
async def update_current_tenant(
    body: TenantUpdate,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    membership: TenantMembership = Depends(get_tenant_membership),
    db: AsyncSession = Depends(get_db),
):
    tenant = await tenant_service.update_tenant(
        db, tenant_id, membership, body.name, body.settings
    )
    return TenantResponse.model_validate(tenant)


@router.get("/current/members", response_model=list[MemberResponse])
async def list_members(
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    members = await tenant_service.get_members(db, tenant_id)
    return [MemberResponse(**m) for m in members]


@router.post("/current/invite", response_model=MemberResponse)
async def invite_member(
    body: InviteMemberRequest,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    membership: TenantMembership = Depends(get_tenant_membership),
    db: AsyncSession = Depends(get_db),
):
    member = await tenant_service.invite_member(
        db, tenant_id, body.email, body.role, membership
    )
    return MemberResponse(**member)


@router.patch("/current/members/{user_id}", response_model=MemberResponse)
async def update_member_role(
    user_id: uuid.UUID,
    body: UpdateMemberRoleRequest,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    membership: TenantMembership = Depends(get_tenant_membership),
    db: AsyncSession = Depends(get_db),
):
    member = await tenant_service.update_member_role(
        db=db,
        tenant_id=tenant_id,
        target_user_id=user_id,
        new_role=body.role,
        actor_membership=membership,
    )
    return MemberResponse(**member)


@router.delete("/current/members/{user_id}", status_code=204)
async def remove_member(
    user_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    membership: TenantMembership = Depends(get_tenant_membership),
    db: AsyncSession = Depends(get_db),
):
    await tenant_service.remove_member(
        db=db,
        tenant_id=tenant_id,
        target_user_id=user_id,
        actor_membership=membership,
    )
