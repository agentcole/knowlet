import uuid

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.database import get_db
from app.models.user import User
from app.models.tenant_membership import TenantMembership


async def get_current_user(
    authorization: str = Header(..., alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization.startswith("Bearer "):
        raise UnauthorizedError("Invalid authorization header")

    token = authorization[7:]
    payload = decode_token(token)
    user_id = payload.get("sub")
    token_type = payload.get("type")

    if not user_id or token_type != "access":
        raise UnauthorizedError("Invalid or expired token")

    result = await db.execute(
        select(User)
        .options(selectinload(User.memberships).selectinload(TenantMembership.tenant))
        .where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise UnauthorizedError("User not found or inactive")
    return user


async def get_tenant_id(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    current_user: User = Depends(get_current_user),
) -> uuid.UUID:
    tenant_id = uuid.UUID(x_tenant_id)
    membership = next(
        (m for m in current_user.memberships if m.tenant_id == tenant_id),
        None,
    )
    if not membership:
        raise ForbiddenError("Not a member of this tenant")
    return tenant_id


async def get_tenant_membership(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    current_user: User = Depends(get_current_user),
) -> TenantMembership:
    tenant_id = uuid.UUID(x_tenant_id)
    membership = next(
        (m for m in current_user.memberships if m.tenant_id == tenant_id),
        None,
    )
    if not membership:
        raise ForbiddenError("Not a member of this tenant")
    return membership
