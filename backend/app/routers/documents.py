import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.database import get_db
from app.dependencies import get_current_user, get_tenant_id, get_tenant_membership
from app.models.tenant_membership import TenantMembership, TenantRole
from app.models.user import User
from app.schemas.document import (
    DocumentChunkResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentWikiApprovalRequest,
    DocumentWikiWorkflowResponse,
)
from app.services import document_service

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentResponse, status_code=202)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    file_data = await file.read()
    file_type = file.filename.rsplit(".", 1)[-1].lower() if file.filename else "unknown"

    doc = await document_service.upload_document(
        db,
        tenant_id,
        current_user.id,
        file.filename or "untitled",
        file_type,
        file_data,
        current_user.default_language,
    )

    # Dispatch Celery task
    try:
        from app.workers.document_tasks import process_document
        process_document.delay(
            str(doc.id),
            str(tenant_id),
            current_user.default_language,
        )
    except Exception:
        pass  # Celery not running, process manually later

    return DocumentResponse.model_validate(doc)


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    docs, total = await document_service.list_documents(
        db, tenant_id, page, page_size, status
    )
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    doc = await document_service.get_document(db, tenant_id, document_id)
    return DocumentResponse.model_validate(doc)


@router.get("/{document_id}/content")
async def get_document_content(
    document_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    doc = await document_service.get_document(db, tenant_id, document_id)
    return {"markdown_content": doc.markdown_content}


@router.get("/{document_id}/chunks", response_model=list[DocumentChunkResponse])
async def get_document_chunks(
    document_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    chunks = await document_service.get_document_chunks(db, tenant_id, document_id)
    return [DocumentChunkResponse.model_validate(c) for c in chunks]


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    await document_service.delete_document(db, tenant_id, document_id)


@router.post("/{document_id}/reprocess", status_code=202)
async def reprocess_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    doc = await document_service.get_document(db, tenant_id, document_id)
    try:
        from app.workers.document_tasks import process_document
        process_document.delay(
            str(doc.id),
            str(tenant_id),
            current_user.default_language,
        )
    except Exception:
        pass
    return {"status": "reprocessing"}


@router.get(
    "/{document_id}/wiki-workflow", response_model=DocumentWikiWorkflowResponse
)
async def get_document_wiki_workflow(
    document_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    workflow = await document_service.get_document_wiki_workflow(
        db, tenant_id, document_id
    )
    return DocumentWikiWorkflowResponse.model_validate(workflow)


@router.post(
    "/{document_id}/wiki-approve", response_model=DocumentWikiWorkflowResponse
)
async def approve_document_wiki(
    document_id: uuid.UUID,
    body: DocumentWikiApprovalRequest,
    current_user: User = Depends(get_current_user),
    membership: TenantMembership = Depends(get_tenant_membership),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    if membership.role not in (TenantRole.OWNER, TenantRole.ADMIN):
        raise ForbiddenError("Only admins can approve wiki updates")

    workflow = await document_service.approve_document_wiki(
        db,
        tenant_id=tenant_id,
        document_id=document_id,
        approver_id=current_user.id,
        placement_override=(
            body.placement.model_dump() if body.placement is not None else None
        ),
        revision_note=body.revision_note,
    )
    return DocumentWikiWorkflowResponse.model_validate(workflow)
