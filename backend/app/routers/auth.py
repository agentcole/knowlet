from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    MeResponse,
    MembershipResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserPreferencesUpdateRequest,
    UserResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user, tenant, access_token, refresh_token = await auth_service.register_user(
        db,
        body.email,
        body.password,
        body.full_name,
        body.tenant_name,
        body.default_language,
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user, access_token, refresh_token = await auth_service.login_user(
        db, body.email, body.password
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    access_token, refresh_token = await auth_service.refresh_tokens(
        db, body.refresh_token
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user)):
    return MeResponse(
        user=UserResponse.model_validate(current_user),
        memberships=[
            MembershipResponse(
                tenant_id=m.tenant_id,
                tenant_name=m.tenant.name,
                tenant_slug=m.tenant.slug,
                role=m.role.value,
            )
            for m in current_user.memberships
        ],
    )


@router.patch("/preferences", response_model=UserResponse)
async def update_preferences(
    body: UserPreferencesUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = await auth_service.update_user_preferences(
        db,
        current_user,
        default_language=body.default_language,
    )
    return UserResponse.model_validate(user)
