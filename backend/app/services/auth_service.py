import uuid
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.language import normalize_language
from app.models.tenant import Tenant
from app.models.tenant_membership import TenantMembership, TenantRole
from app.models.user import User


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower().strip())
    return re.sub(r"[-\s]+", "-", slug)


async def register_user(
    db: AsyncSession,
    email: str,
    password: str,
    full_name: str,
    tenant_name: str,
    default_language: str = "en",
) -> tuple[User, Tenant, str, str]:
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise BadRequestError("Email already registered")

    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        default_language=normalize_language(default_language),
    )
    db.add(user)
    await db.flush()

    slug = _slugify(tenant_name)
    existing_tenant = await db.execute(select(Tenant).where(Tenant.slug == slug))
    if existing_tenant.scalar_one_or_none():
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    tenant = Tenant(name=tenant_name, slug=slug)
    db.add(tenant)
    await db.flush()

    membership = TenantMembership(
        user_id=user.id,
        tenant_id=tenant.id,
        role=TenantRole.OWNER,
    )
    db.add(membership)
    await db.flush()

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    return user, tenant, access_token, refresh_token


async def login_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> tuple[User, str, str]:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password):
        raise UnauthorizedError("Invalid email or password")

    if not user.is_active:
        raise UnauthorizedError("Account is disabled")

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    return user, access_token, refresh_token


async def refresh_tokens(
    db: AsyncSession,
    refresh_token: str,
) -> tuple[str, str]:
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise UnauthorizedError("Invalid refresh token")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid refresh token")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise UnauthorizedError("User not found or inactive")

    new_access = create_access_token({"sub": str(user.id)})
    new_refresh = create_refresh_token({"sub": str(user.id)})
    return new_access, new_refresh


async def update_user_preferences(
    db: AsyncSession,
    user: User,
    default_language: str | None = None,
) -> User:
    if default_language is not None:
        user.default_language = normalize_language(default_language)
    await db.flush()
    return user
