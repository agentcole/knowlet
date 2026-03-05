import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.language import normalize_language
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.models.wiki import WikiPage
from app.services.storage_service import storage
from app.services.vector_service import get_tenant_store
from app.services import wiki_service
from app.services.wiki_workflow import get_workflow, normalize_placement, set_workflow


async def upload_document(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str,
    file_type: str,
    file_data: bytes,
    preferred_language: str | None = None,
) -> Document:
    storage_path = await storage.save(tenant_id, "documents", filename, file_data)
    metadata = set_workflow(
        None,
        {
            "state": "processing",
            "language": normalize_language(preferred_language),
        },
    )

    doc = Document(
        tenant_id=tenant_id,
        uploaded_by=user_id,
        filename=filename,
        file_type=file_type,
        storage_path=storage_path,
        status=DocumentStatus.UPLOADED,
        doc_metadata=metadata,
    )
    db.add(doc)
    await db.flush()
    return doc


async def get_document(
    db: AsyncSession, tenant_id: uuid.UUID, document_id: uuid.UUID
) -> Document:
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundError("Document not found")
    return doc


async def list_documents(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
) -> tuple[list[Document], int]:
    query = select(Document).where(Document.tenant_id == tenant_id)
    count_query = select(func.count()).select_from(Document).where(Document.tenant_id == tenant_id)

    if status:
        query = query.where(Document.status == status)
        count_query = count_query.where(Document.status == status)

    query = query.order_by(Document.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    docs = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return docs, total


async def get_document_chunks(
    db: AsyncSession, tenant_id: uuid.UUID, document_id: uuid.UUID
) -> list[DocumentChunk]:
    result = await db.execute(
        select(DocumentChunk)
        .where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.tenant_id == tenant_id,
        )
        .order_by(DocumentChunk.chunk_index)
    )
    return list(result.scalars().all())


async def delete_document(
    db: AsyncSession, tenant_id: uuid.UUID, document_id: uuid.UUID
) -> None:
    doc = await get_document(db, tenant_id, document_id)

    # Remove vector entries for this document's chunks first to avoid stale retrieval hits.
    chunk_result = await db.execute(
        select(DocumentChunk.id).where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.tenant_id == tenant_id,
        )
    )
    chunk_ids = [str(row[0]) for row in chunk_result.all()]
    if chunk_ids:
        try:
            store = get_tenant_store(tenant_id)
            for chunk_id in chunk_ids:
                store.delete(chunk_id)
        except Exception:
            # Vector index cleanup failure should not block source-of-truth deletion.
            pass

    # Remove source document references from wiki pages.
    doc_ref = str(document_id)
    pages_result = await db.execute(
        select(WikiPage).where(WikiPage.tenant_id == tenant_id)
    )
    for page in pages_result.scalars().all():
        source_documents = list(page.source_documents or [])
        if doc_ref in source_documents:
            page.source_documents = [ref for ref in source_documents if ref != doc_ref]

    await storage.delete(doc.storage_path)
    await db.delete(doc)
    await db.flush()


async def update_document_status(
    db: AsyncSession, document_id: uuid.UUID, status: DocumentStatus
) -> None:
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if doc:
        doc.status = status
        await db.flush()


def _default_workflow_state(doc: Document) -> dict:
    if doc.status in (DocumentStatus.UPLOADED, DocumentStatus.PROCESSING):
        return {"state": "processing"}
    if doc.status == DocumentStatus.FAILED:
        return {"state": "failed"}
    return {"state": "pending_approval"}


def _save_workflow(doc: Document, workflow: dict) -> None:
    doc.doc_metadata = set_workflow(doc.doc_metadata, workflow)


async def _ensure_suggestion(
    db: AsyncSession, tenant_id: uuid.UUID, doc: Document, workflow: dict
) -> dict:
    workflow["language"] = normalize_language(workflow.get("language"))

    if doc.status != DocumentStatus.PROCESSED or not doc.markdown_content:
        return workflow

    suggestion = normalize_placement(workflow.get("suggestion"))
    if suggestion:
        workflow["suggestion"] = suggestion
        return workflow

    suggested = await wiki_service.suggest_wiki_placement(
        db,
        tenant_id=tenant_id,
        filename=doc.filename,
        content=doc.markdown_content,
        preferred_language=workflow["language"],
    )
    workflow["suggestion"] = suggested
    if workflow.get("state") in (None, "processing"):
        workflow["state"] = "pending_approval"
    workflow.pop("error", None)
    return workflow


async def get_document_wiki_workflow(
    db: AsyncSession, tenant_id: uuid.UUID, document_id: uuid.UUID
) -> dict:
    doc = await get_document(db, tenant_id, document_id)
    workflow = get_workflow(doc.doc_metadata)
    if "state" not in workflow:
        workflow = _default_workflow_state(doc)

    workflow = await _ensure_suggestion(db, tenant_id, doc, workflow)
    if "placement" in workflow:
        normalized = normalize_placement(workflow.get("placement"))
        if normalized:
            workflow["placement"] = normalized

    _save_workflow(doc, workflow)
    await db.flush()
    return workflow


async def approve_document_wiki(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    document_id: uuid.UUID,
    approver_id: uuid.UUID,
    placement_override: dict | None = None,
    revision_note: str | None = None,
) -> dict:
    doc = await get_document(db, tenant_id, document_id)
    if doc.status != DocumentStatus.PROCESSED:
        raise BadRequestError("Document must be processed before wiki approval")
    if not doc.markdown_content:
        raise BadRequestError("Document has no extracted content to publish")

    workflow = get_workflow(doc.doc_metadata)
    if "state" not in workflow:
        workflow = _default_workflow_state(doc)
    workflow = await _ensure_suggestion(db, tenant_id, doc, workflow)

    suggestion = normalize_placement(workflow.get("suggestion"))
    approved_placement = normalize_placement(placement_override) or suggestion
    if not approved_placement:
        raise BadRequestError("No wiki placement suggestion available yet")

    pages = await wiki_service.apply_document_to_wiki(
        db,
        tenant_id=tenant_id,
        document=doc,
        placement=approved_placement,
        revision_note=revision_note,
        created_by=approver_id,
    )

    workflow.update(
        {
            "state": "published",
            "placement": approved_placement,
            "approved_by": str(approver_id),
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "published_page_ids": [str(page.id) for page in pages],
            "revision_note": revision_note,
            "error": None,
        }
    )
    _save_workflow(doc, workflow)
    await db.flush()
    return workflow
