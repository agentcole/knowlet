import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.tenant import Tenant
from app.models.tenant_membership import TenantMembership, TenantRole
from app.models.user import User


async def get_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise NotFoundError("Tenant not found")
    return tenant


async def update_tenant(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    membership: TenantMembership,
    name: str | None = None,
    settings: dict | None = None,
) -> Tenant:
    if membership.role not in (TenantRole.OWNER, TenantRole.ADMIN):
        raise ForbiddenError("Only owners and admins can update tenant settings")

    tenant = await get_tenant(db, tenant_id)
    if name is not None:
        tenant.name = name
    if settings is not None:
        tenant.settings = settings
    await db.flush()
    return tenant


async def get_members(db: AsyncSession, tenant_id: uuid.UUID) -> list[dict]:
    result = await db.execute(
        select(TenantMembership)
        .options(selectinload(TenantMembership.user))
        .where(TenantMembership.tenant_id == tenant_id)
    )
    memberships = result.scalars().all()
    return [
        {
            "user_id": m.user.id,
            "email": m.user.email,
            "full_name": m.user.full_name,
            "role": m.role.value,
        }
        for m in memberships
    ]


async def invite_member(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    email: str,
    role: str,
    inviter_membership: TenantMembership,
) -> dict:
    if inviter_membership.role not in (TenantRole.OWNER, TenantRole.ADMIN):
        raise ForbiddenError("Only owners and admins can invite members")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise BadRequestError("User not found. They must register first.")

    existing = await db.execute(
        select(TenantMembership).where(
            TenantMembership.user_id == user.id,
            TenantMembership.tenant_id == tenant_id,
        )
    )
    if existing.scalar_one_or_none():
        raise BadRequestError("User is already a member")

    membership = TenantMembership(
        user_id=user.id,
        tenant_id=tenant_id,
        role=TenantRole(role),
    )
    db.add(membership)
    await db.flush()

    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": role,
    }
