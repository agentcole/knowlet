import os
import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_tenant_id, get_tenant_membership
from app.models.tenant_membership import TenantMembership, TenantRole
from app.models.user import User
from app.core.exceptions import ForbiddenError
from app.schemas.wiki import (
    WikiCategoryCreate,
    WikiCategoryResponse,
    WikiCategoryUpdate,
    WikiAssetListResponse,
    WikiAssetResponse,
    WikiPageCreate,
    WikiPageRevisionResponse,
    WikiPageResponse,
    WikiPageUpdate,
    WikiTreeResponse,
)
from app.services import wiki_service

router = APIRouter(prefix="/api/v1/wiki", tags=["wiki"])


def _asset_response(asset) -> WikiAssetResponse:
    return WikiAssetResponse(
        id=asset.id,
        filename=asset.filename,
        content_type=asset.content_type,
        file_size=asset.file_size,
        created_at=asset.created_at,
        content_url=wiki_service.asset_content_url(asset.id),
    )


@router.get("/tree", response_model=WikiTreeResponse)
async def get_wiki_tree(
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    tree = await wiki_service.get_wiki_tree(db, tenant_id)
    return WikiTreeResponse(**tree)


@router.get("/assets", response_model=WikiAssetListResponse)
async def list_assets(
    q: str | None = Query(None, min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    items, total = await wiki_service.list_assets(db, tenant_id, q, page, page_size)
    return WikiAssetListResponse(
        items=[_asset_response(asset) for asset in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/assets/upload", response_model=WikiAssetResponse)
async def upload_asset(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    data = await file.read()
    asset = await wiki_service.create_asset(
        db=db,
        tenant_id=tenant_id,
        uploaded_by=current_user.id,
        filename=file.filename or "asset",
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )
    return _asset_response(asset)


@router.get("/assets/{asset_id}/content")
async def get_asset_content(
    asset_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    asset = await wiki_service.get_asset(db, tenant_id, asset_id)
    return FileResponse(
        path=asset.storage_path,
        media_type=asset.content_type,
        filename=os.path.basename(asset.filename),
    )


@router.delete("/assets/{asset_id}", status_code=204)
async def delete_asset(
    asset_id: uuid.UUID,
    membership: TenantMembership = Depends(get_tenant_membership),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    if membership.role not in (TenantRole.OWNER, TenantRole.ADMIN):
        raise ForbiddenError("Only admins can delete wiki assets")
    await wiki_service.delete_asset(db, tenant_id, asset_id)


@router.post("/categories", response_model=WikiCategoryResponse)
async def create_category(
    body: WikiCategoryCreate,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    category = await wiki_service.create_category(
        db, tenant_id, body.name, body.parent_id, body.sort_order
    )
    return WikiCategoryResponse.model_validate(category)


@router.put("/categories/{category_id}", response_model=WikiCategoryResponse)
async def update_category(
    category_id: uuid.UUID,
    body: WikiCategoryUpdate,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    fields = body.model_fields_set
    category = await wiki_service.update_category(
        db,
        tenant_id=tenant_id,
        category_id=category_id,
        name=body.name,
        parent_id=body.parent_id,
        sort_order=body.sort_order,
        name_set="name" in fields,
        parent_id_set="parent_id" in fields,
        sort_order_set="sort_order" in fields,
    )
    return WikiCategoryResponse.model_validate(category)


@router.delete("/categories/{category_id}", status_code=204)
async def delete_category(
    category_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    await wiki_service.delete_category(db, tenant_id, category_id)


@router.post("/pages", response_model=WikiPageResponse)
async def create_page(
    body: WikiPageCreate,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    page = await wiki_service.create_page(
        db,
        tenant_id,
        body.title,
        body.markdown_content,
        body.category_id,
        body.sort_order,
    )
    return WikiPageResponse.model_validate(page)


@router.get("/pages/{page_id}", response_model=WikiPageResponse)
async def get_page(
    page_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    page = await wiki_service.get_page(db, tenant_id, page_id)
    return WikiPageResponse.model_validate(page)


@router.put("/pages/{page_id}", response_model=WikiPageResponse)
async def update_page(
    page_id: uuid.UUID,
    body: WikiPageUpdate,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    page = await wiki_service.update_page(
        db,
        tenant_id,
        page_id,
        body.title,
        body.markdown_content,
        body.category_id,
        body.sort_order,
        body.change_note,
        current_user.id,
        category_id_set="category_id" in body.model_fields_set,
        sort_order_set="sort_order" in body.model_fields_set,
    )
    return WikiPageResponse.model_validate(page)


@router.delete("/pages/{page_id}", status_code=204)
async def delete_page(
    page_id: uuid.UUID,
    membership: TenantMembership = Depends(get_tenant_membership),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    if membership.role not in (TenantRole.OWNER, TenantRole.ADMIN):
        raise ForbiddenError("Only admins can delete wiki pages")
    await wiki_service.delete_page(db, tenant_id, page_id)


@router.get("/search", response_model=list[WikiPageResponse])
async def search_wiki(
    q: str = Query(..., min_length=1),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    pages = await wiki_service.search_wiki(db, tenant_id, q)
    return [WikiPageResponse.model_validate(p) for p in pages]


@router.post("/generate", status_code=202)
async def generate_wiki(
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    membership: TenantMembership = Depends(get_tenant_membership),
    db: AsyncSession = Depends(get_db),
):
    if membership.role not in (TenantRole.OWNER, TenantRole.ADMIN):
        raise ForbiddenError("Only admins can trigger wiki regeneration")
    try:
        from app.workers.wiki_tasks import regenerate_wiki
        regenerate_wiki.delay(str(tenant_id))
    except Exception:
        pass
    return {"status": "regeneration_queued"}


@router.post("/reindex", status_code=202)
async def reindex_wiki(
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    membership: TenantMembership = Depends(get_tenant_membership),
):
    if membership.role not in (TenantRole.OWNER, TenantRole.ADMIN):
        raise ForbiddenError("Only admins can trigger wiki reindexing")
    try:
        from app.workers.wiki_tasks import reindex_wiki_vectors

        reindex_wiki_vectors.delay(str(tenant_id))
    except Exception:
        pass
    return {"status": "reindex_queued"}


@router.get(
    "/pages/{page_id}/revisions", response_model=list[WikiPageRevisionResponse]
)
async def list_page_revisions(
    page_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    revisions = await wiki_service.list_page_revisions(db, tenant_id, page_id)
    return [WikiPageRevisionResponse.model_validate(revision) for revision in revisions]


@router.post(
    "/pages/{page_id}/revisions/{revision_id}/restore",
    response_model=WikiPageResponse,
)
async def restore_page_revision(
    page_id: uuid.UUID,
    revision_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    membership: TenantMembership = Depends(get_tenant_membership),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    if membership.role not in (TenantRole.OWNER, TenantRole.ADMIN):
        raise ForbiddenError("Only admins can restore wiki revisions")

    restored = await wiki_service.restore_page_revision(
        db,
        tenant_id=tenant_id,
        page_id=page_id,
        revision_id=revision_id,
        restored_by=current_user.id,
    )
    return WikiPageResponse.model_validate(restored)
