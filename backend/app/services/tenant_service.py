import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.tenant import Tenant
from app.models.tenant_membership import TenantMembership, TenantRole
from app.models.user import User
from app.services.email_service import (
    send_member_invited_email,
    send_member_removed_email,
    send_member_role_changed_email,
)

logger = logging.getLogger(__name__)


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
    role: TenantRole,
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
        role=role,
    )
    db.add(membership)
    await db.flush()

    try:
        tenant = await get_tenant(db, tenant_id)
        await send_member_invited_email(
            to_email=user.email,
            full_name=user.full_name,
            tenant_name=tenant.name,
            role=role.value,
        )
    except Exception:
        logger.exception("Failed to send invited member notification")

    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": role,
    }


async def update_member_role(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    target_user_id: uuid.UUID,
    new_role: TenantRole,
    actor_membership: TenantMembership,
) -> dict:
    if actor_membership.role not in (TenantRole.OWNER, TenantRole.ADMIN):
        raise ForbiddenError("Only owners and admins can change member roles")

    if actor_membership.user_id == target_user_id:
        raise BadRequestError("You cannot change your own role")

    result = await db.execute(
        select(TenantMembership)
        .options(selectinload(TenantMembership.user))
        .where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == target_user_id,
        )
    )
    target_membership = result.scalar_one_or_none()
    if not target_membership:
        raise NotFoundError("Member not found")

    # Admins cannot modify owners, and only owners can assign owner role.
    if actor_membership.role != TenantRole.OWNER:
        if target_membership.role == TenantRole.OWNER:
            raise ForbiddenError("Only owners can modify owner memberships")
        if new_role == TenantRole.OWNER:
            raise ForbiddenError("Only owners can assign the owner role")

    if target_membership.role == new_role:
        user = target_membership.user
        return {
            "user_id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": target_membership.role,
        }

    previous_role = target_membership.role
    if target_membership.role == TenantRole.OWNER and new_role != TenantRole.OWNER:
        owners_count = await db.scalar(
            select(func.count())
            .select_from(TenantMembership)
            .where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.role == TenantRole.OWNER,
            )
        )
        if owners_count is None or owners_count <= 1:
            raise BadRequestError("A tenant must have at least one owner")

    target_membership.role = new_role
    await db.flush()

    user = target_membership.user
    try:
        tenant = await get_tenant(db, tenant_id)
        await send_member_role_changed_email(
            to_email=user.email,
            full_name=user.full_name,
            tenant_name=tenant.name,
            previous_role=previous_role.value,
            new_role=new_role.value,
        )
    except Exception:
        logger.exception("Failed to send role change notification")

    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": target_membership.role,
    }


async def remove_member(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    target_user_id: uuid.UUID,
    actor_membership: TenantMembership,
) -> None:
    if actor_membership.role not in (TenantRole.OWNER, TenantRole.ADMIN):
        raise ForbiddenError("Only owners and admins can remove members")

    if actor_membership.user_id == target_user_id:
        raise BadRequestError("You cannot remove yourself from the tenant")

    result = await db.execute(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == target_user_id,
        )
    )
    target_membership = result.scalar_one_or_none()
    if not target_membership:
        raise NotFoundError("Member not found")

    if actor_membership.role != TenantRole.OWNER and target_membership.role == TenantRole.OWNER:
        raise ForbiddenError("Only owners can remove owners")

    if target_membership.role == TenantRole.OWNER:
        owners_count = await db.scalar(
            select(func.count())
            .select_from(TenantMembership)
            .where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.role == TenantRole.OWNER,
            )
        )
        if owners_count is None or owners_count <= 1:
            raise BadRequestError("A tenant must have at least one owner")

    user = await db.get(User, target_user_id)
    tenant = await get_tenant(db, tenant_id)
    await db.delete(target_membership)
    await db.flush()

    if user:
        try:
            await send_member_removed_email(
                to_email=user.email,
                full_name=user.full_name,
                tenant_name=tenant.name,
            )
        except Exception:
            logger.exception("Failed to send member removal notification")
