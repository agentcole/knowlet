import json
import re
import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.document import DocumentChunk
from app.models.wiki import WikiCategory, WikiPage, WikiPageRevision
from app.services.llm_service import (
    WIKI_ORGANIZE_PROMPT,
    WIKI_PLACEMENT_PROMPT,
    generate_text,
    with_output_language,
)
from app.services.storage_service import storage
from app.services.vector_service import get_tenant_store
from app.services.wiki_workflow import DEFAULT_CATEGORY, normalize_placement


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower().strip())
    return re.sub(r"[-\s]+", "-", slug)


def _strip_json_fences(text: str) -> str:
    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
    return clean


def _derive_page_title(filename: str) -> str:
    base = filename.rsplit(".", 1)[0].strip() if filename else ""
    if not base:
        return "Imported Content"
    return " ".join(part.capitalize() for part in re.split(r"[_\-]+", base))


async def _get_or_create_category(
    db: AsyncSession, tenant_id: uuid.UUID, category_name: str
) -> WikiCategory:
    desired = category_name.strip() or DEFAULT_CATEGORY
    category_slug = _slugify(desired)

    existing = await db.execute(
        select(WikiCategory).where(
            WikiCategory.tenant_id == tenant_id,
            WikiCategory.slug == category_slug,
        )
    )
    category = existing.scalar_one_or_none()
    if category:
        return category

    return await create_category(db, tenant_id, desired)


async def _find_page_by_title(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    title: str,
    category_id: uuid.UUID | None = None,
) -> WikiPage | None:
    query = select(WikiPage).where(
        WikiPage.tenant_id == tenant_id,
        WikiPage.title.ilike(title),
    )
    if category_id is not None:
        query = query.where(WikiPage.category_id == category_id)
    result = await db.execute(query)
    return result.scalars().first()


async def _next_available_title(
    db: AsyncSession, tenant_id: uuid.UUID, desired_title: str
) -> str:
    title = desired_title.strip() or "Imported Content"
    current = title
    suffix = 2
    while await _find_page_by_title(db, tenant_id, current):
        current = f"{title} ({suffix})"
        suffix += 1
    return current


async def _snapshot_revision(
    db: AsyncSession,
    page: WikiPage,
    change_note: str | None = None,
    created_by: uuid.UUID | None = None,
) -> WikiPageRevision:
    revision = WikiPageRevision(
        tenant_id=page.tenant_id,
        page_id=page.id,
        version=page.version,
        title=page.title,
        markdown_content=page.markdown_content,
        change_note=change_note,
        created_by=created_by,
    )
    db.add(revision)
    await db.flush()
    return revision


def _append_source_document(page: WikiPage, document_id: uuid.UUID) -> None:
    source_documents = list(page.source_documents or [])
    doc_ref = str(document_id)
    if doc_ref not in source_documents:
        source_documents.append(doc_ref)
    page.source_documents = source_documents


async def _document_is_referenced_elsewhere(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    document_ref: str,
    excluding_page_id: uuid.UUID,
) -> bool:
    result = await db.execute(
        select(WikiPage.id)
        .where(
            WikiPage.tenant_id == tenant_id,
            WikiPage.id != excluding_page_id,
            WikiPage.source_documents.contains([document_ref]),
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _remove_document_vectors(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    document_id: uuid.UUID,
) -> None:
    chunk_result = await db.execute(
        select(DocumentChunk).where(
            DocumentChunk.tenant_id == tenant_id,
            DocumentChunk.document_id == document_id,
        )
    )
    chunks = list(chunk_result.scalars().all())
    if not chunks:
        return

    try:
        store = get_tenant_store(tenant_id)
        for chunk in chunks:
            store.delete(str(chunk.id))
            chunk.vector_indexed = False
    except Exception:
        # Keep DB state untouched if vector store cleanup fails unexpectedly.
        pass


async def _next_category_sort_order(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    parent_id: uuid.UUID | None,
) -> int:
    query = select(func.max(WikiCategory.sort_order)).where(
        WikiCategory.tenant_id == tenant_id
    )
    if parent_id is None:
        query = query.where(WikiCategory.parent_id.is_(None))
    else:
        query = query.where(WikiCategory.parent_id == parent_id)
    result = await db.execute(query)
    maximum = result.scalar_one_or_none()
    return int((maximum if maximum is not None else -1) + 1)


async def _next_page_sort_order(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    category_id: uuid.UUID | None,
) -> int:
    query = select(func.max(WikiPage.sort_order)).where(
        WikiPage.tenant_id == tenant_id
    )
    if category_id is None:
        query = query.where(WikiPage.category_id.is_(None))
    else:
        query = query.where(WikiPage.category_id == category_id)
    result = await db.execute(query)
    maximum = result.scalar_one_or_none()
    return int((maximum if maximum is not None else -1) + 1)


async def get_wiki_tree(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    cat_result = await db.execute(
        select(WikiCategory)
        .where(WikiCategory.tenant_id == tenant_id)
        .order_by(WikiCategory.sort_order)
    )
    categories = list(cat_result.scalars().all())

    page_result = await db.execute(
        select(WikiPage).where(WikiPage.tenant_id == tenant_id)
    )
    pages = list(page_result.scalars().all())

    cat_map = {c.id: c for c in categories}
    cat_pages = {}
    uncategorized = []

    for p in pages:
        if p.category_id and p.category_id in cat_map:
            cat_pages.setdefault(p.category_id, []).append(p)
        else:
            uncategorized.append(p)

    for category_pages in cat_pages.values():
        category_pages.sort(key=lambda page: (page.sort_order, page.title.lower()))
    uncategorized.sort(key=lambda page: (page.sort_order, page.title.lower()))

    def build_tree(parent_id=None):
        children = [c for c in categories if c.parent_id == parent_id]
        tree = []
        for c in sorted(children, key=lambda x: (x.sort_order, x.name.lower())):
            tree.append({
                "id": c.id,
                "name": c.name,
                "slug": c.slug,
                "sort_order": c.sort_order,
                "children": build_tree(c.id),
                "pages": cat_pages.get(c.id, []),
            })
        return tree

    return {
        "categories": build_tree(),
        "uncategorized_pages": uncategorized,
    }


async def create_category(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    name: str,
    parent_id: uuid.UUID | None = None,
    sort_order: int | None = None,
) -> WikiCategory:
    if parent_id is not None:
        parent = await db.execute(
            select(WikiCategory).where(
                WikiCategory.id == parent_id,
                WikiCategory.tenant_id == tenant_id,
            )
        )
        if parent.scalar_one_or_none() is None:
            raise NotFoundError("Parent category not found")

    effective_sort_order = (
        sort_order
        if sort_order is not None
        else await _next_category_sort_order(db, tenant_id, parent_id)
    )

    category = WikiCategory(
        tenant_id=tenant_id,
        name=name,
        slug=_slugify(name),
        parent_id=parent_id,
        sort_order=effective_sort_order,
    )
    db.add(category)
    await db.flush()
    return category


async def get_category(
    db: AsyncSession, tenant_id: uuid.UUID, category_id: uuid.UUID
) -> WikiCategory:
    result = await db.execute(
        select(WikiCategory).where(
            WikiCategory.id == category_id,
            WikiCategory.tenant_id == tenant_id,
        )
    )
    category = result.scalar_one_or_none()
    if category is None:
        raise NotFoundError("Wiki category not found")
    return category


async def _collect_descendants(
    db: AsyncSession, tenant_id: uuid.UUID, category_id: uuid.UUID
) -> set[uuid.UUID]:
    descendants: set[uuid.UUID] = set()
    queue: list[uuid.UUID] = [category_id]
    while queue:
        current = queue.pop(0)
        result = await db.execute(
            select(WikiCategory.id).where(
                WikiCategory.tenant_id == tenant_id,
                WikiCategory.parent_id == current,
            )
        )
        child_ids = [row[0] for row in result.all()]
        for child_id in child_ids:
            if child_id not in descendants:
                descendants.add(child_id)
                queue.append(child_id)
    return descendants


async def update_category(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    category_id: uuid.UUID,
    name: str | None = None,
    parent_id: uuid.UUID | None = None,
    sort_order: int | None = None,
    name_set: bool = False,
    parent_id_set: bool = False,
    sort_order_set: bool = False,
) -> WikiCategory:
    category = await get_category(db, tenant_id, category_id)
    parent_changed = False

    if name_set:
        if not name:
            raise BadRequestError("Category name cannot be empty")
        category.name = name
        category.slug = _slugify(name)

    if parent_id_set:
        if parent_id is not None:
            if parent_id == category_id:
                raise BadRequestError("Category cannot be its own parent")

            parent = await get_category(db, tenant_id, parent_id)
            descendants = await _collect_descendants(db, tenant_id, category_id)
            if parent.id in descendants:
                raise BadRequestError("Cannot move category under one of its descendants")
            if category.parent_id != parent.id:
                parent_changed = True
            category.parent_id = parent.id
        else:
            if category.parent_id is not None:
                parent_changed = True
            category.parent_id = None

    if sort_order_set:
        if sort_order is None:
            raise BadRequestError("sort_order cannot be null")
        category.sort_order = sort_order
    elif parent_changed:
        category.sort_order = await _next_category_sort_order(
            db,
            tenant_id,
            category.parent_id,
        )

    await db.flush()
    return category


async def delete_category(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    category_id: uuid.UUID,
) -> None:
    category = await get_category(db, tenant_id, category_id)
    target_parent_id = category.parent_id

    child_result = await db.execute(
        select(WikiCategory).where(
            WikiCategory.tenant_id == tenant_id,
            WikiCategory.parent_id == category.id,
        )
    )
    for child in child_result.scalars().all():
        child.parent_id = target_parent_id

    page_result = await db.execute(
        select(WikiPage).where(
            WikiPage.tenant_id == tenant_id,
            WikiPage.category_id == category.id,
        )
    )
    for page in page_result.scalars().all():
        page.category_id = target_parent_id

    await db.delete(category)
    await db.flush()


async def create_page(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    title: str,
    markdown_content: str = "",
    category_id: uuid.UUID | None = None,
    sort_order: int | None = None,
) -> WikiPage:
    if category_id is not None:
        await get_category(db, tenant_id, category_id)

    effective_sort_order = (
        sort_order
        if sort_order is not None
        else await _next_page_sort_order(db, tenant_id, category_id)
    )

    slug = _slugify(title)
    file_path = await storage.save_text(
        tenant_id, "wiki", f"{slug}.md", markdown_content
    )
    page = WikiPage(
        tenant_id=tenant_id,
        title=title,
        slug=slug,
        category_id=category_id,
        sort_order=effective_sort_order,
        markdown_content=markdown_content,
        file_path=file_path,
    )
    db.add(page)
    await db.flush()
    return page


async def update_page(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    page_id: uuid.UUID,
    title: str | None = None,
    markdown_content: str | None = None,
    category_id: uuid.UUID | None = None,
    sort_order: int | None = None,
    change_note: str | None = None,
    created_by: uuid.UUID | None = None,
    category_id_set: bool = False,
    sort_order_set: bool = False,
) -> WikiPage:
    result = await db.execute(
        select(WikiPage).where(WikiPage.id == page_id, WikiPage.tenant_id == tenant_id)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise NotFoundError("Wiki page not found")

    category_change_requested = category_id_set or category_id is not None
    sort_order_change_requested = sort_order_set or sort_order is not None

    if (
        title is None
        and markdown_content is None
        and not category_change_requested
        and not sort_order_change_requested
    ):
        return page

    await _snapshot_revision(db, page, change_note=change_note, created_by=created_by)

    if title is not None:
        page.title = title
        page.slug = _slugify(title)
    if markdown_content is not None:
        page.markdown_content = markdown_content
    if category_change_requested:
        if category_id is not None:
            await get_category(db, tenant_id, category_id)
        page.category_id = category_id
        if not sort_order_change_requested:
            page.sort_order = await _next_page_sort_order(
                db,
                tenant_id,
                page.category_id,
            )
    if sort_order_change_requested:
        if sort_order is None:
            raise BadRequestError("sort_order cannot be null")
        page.sort_order = sort_order

    page.version += 1
    content_to_store = page.markdown_content
    page.file_path = await storage.save_text(
        tenant_id, "wiki", f"{page.slug}.md", content_to_store
    )

    await db.flush()
    return page


async def get_page(db: AsyncSession, tenant_id: uuid.UUID, page_id: uuid.UUID) -> WikiPage:
    result = await db.execute(
        select(WikiPage).where(WikiPage.id == page_id, WikiPage.tenant_id == tenant_id)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise NotFoundError("Wiki page not found")
    return page


async def delete_page(db: AsyncSession, tenant_id: uuid.UUID, page_id: uuid.UUID) -> None:
    page = await get_page(db, tenant_id, page_id)

    source_documents = list(page.source_documents or [])
    for doc_ref in source_documents:
        if not isinstance(doc_ref, str):
            continue
        if await _document_is_referenced_elsewhere(
            db,
            tenant_id=tenant_id,
            document_ref=doc_ref,
            excluding_page_id=page.id,
        ):
            continue
        try:
            await _remove_document_vectors(db, tenant_id, uuid.UUID(doc_ref))
        except (ValueError, TypeError):
            continue

    if page.file_path:
        await storage.delete(page.file_path)
    await db.delete(page)
    await db.flush()


async def search_wiki(db: AsyncSession, tenant_id: uuid.UUID, query: str) -> list[WikiPage]:
    result = await db.execute(
        select(WikiPage).where(
            WikiPage.tenant_id == tenant_id,
            (WikiPage.title.ilike(f"%{query}%")) | (WikiPage.markdown_content.ilike(f"%{query}%")),
        )
    )
    return list(result.scalars().all())


async def list_page_revisions(
    db: AsyncSession, tenant_id: uuid.UUID, page_id: uuid.UUID
) -> list[WikiPageRevision]:
    result = await db.execute(
        select(WikiPageRevision)
        .where(
            WikiPageRevision.tenant_id == tenant_id,
            WikiPageRevision.page_id == page_id,
        )
        .order_by(desc(WikiPageRevision.created_at))
    )
    return list(result.scalars().all())


async def restore_page_revision(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    page_id: uuid.UUID,
    revision_id: uuid.UUID,
    restored_by: uuid.UUID | None = None,
) -> WikiPage:
    page = await get_page(db, tenant_id, page_id)
    revision_result = await db.execute(
        select(WikiPageRevision).where(
            WikiPageRevision.id == revision_id,
            WikiPageRevision.page_id == page_id,
            WikiPageRevision.tenant_id == tenant_id,
        )
    )
    revision = revision_result.scalar_one_or_none()
    if not revision:
        raise NotFoundError("Revision not found")

    await _snapshot_revision(
        db,
        page,
        change_note=f"Restore from revision v{revision.version}",
        created_by=restored_by,
    )
    page.title = revision.title
    page.slug = _slugify(revision.title)
    page.markdown_content = revision.markdown_content
    page.version += 1
    page.file_path = await storage.save_text(
        tenant_id, "wiki", f"{page.slug}.md", page.markdown_content
    )
    await db.flush()
    return page


async def suggest_wiki_placement(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    filename: str,
    content: str,
    preferred_language: str | None = None,
) -> dict:
    category_result = await db.execute(
        select(WikiCategory.name)
        .where(WikiCategory.tenant_id == tenant_id)
        .order_by(WikiCategory.sort_order.asc(), WikiCategory.name.asc())
        .limit(50)
    )
    page_result = await db.execute(
        select(WikiPage.title)
        .where(WikiPage.tenant_id == tenant_id)
        .order_by(WikiPage.updated_at.desc())
        .limit(100)
    )
    category_names = [name for (name,) in category_result.all()]
    page_titles = [title for (title,) in page_result.all()]

    default = {
        "category_name": category_names[0] if category_names else DEFAULT_CATEGORY,
        "page_title": _derive_page_title(filename),
        "action": "create_new",
        "reasoning": "Fallback suggestion due to placement analysis failure.",
        "confidence": 0.25,
    }

    try:
        response = await generate_text(
            with_output_language(WIKI_PLACEMENT_PROMPT, preferred_language),
            (
                f"Filename: {filename}\n"
                f"Existing categories: {json.dumps(category_names)}\n"
                f"Existing page titles: {json.dumps(page_titles)}\n\n"
                f"Document excerpt:\n{content[:8000]}"
            ),
        )
        parsed = json.loads(_strip_json_fences(response))
        suggestion = normalize_placement(parsed if isinstance(parsed, dict) else None)
        if suggestion:
            return suggestion
    except Exception:
        pass

    return default


async def apply_document_to_wiki(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    document,
    placement: dict,
    revision_note: str | None = None,
    created_by: uuid.UUID | None = None,
) -> list[WikiPage]:
    normalized = normalize_placement(placement)
    if not normalized:
        raise BadRequestError("Invalid wiki placement")
    if not getattr(document, "markdown_content", None):
        raise BadRequestError("Document has no markdown content to publish")

    category = await _get_or_create_category(db, tenant_id, normalized["category_name"])
    page = await _find_page_by_title(db, tenant_id, normalized["page_title"], category.id)
    action = normalized["action"]
    content = document.markdown_content
    current_doc_ref = str(document.id)
    replaced_source_documents: list[str] = []

    if action == "append" and page is not None:
        appended = (
            f"{page.markdown_content.rstrip()}\n\n---\n\n"
            f"## Update from {document.filename}\n\n{content}"
        )
        page = await update_page(
            db,
            tenant_id=tenant_id,
            page_id=page.id,
            markdown_content=appended,
            category_id=category.id,
            change_note=revision_note or f"Append content from {document.filename}",
            created_by=created_by,
        )
    elif action == "replace" and page is not None:
        replaced_source_documents = [
            ref for ref in (page.source_documents or []) if isinstance(ref, str)
        ]
        page = await update_page(
            db,
            tenant_id=tenant_id,
            page_id=page.id,
            title=normalized["page_title"],
            markdown_content=content,
            category_id=category.id,
            change_note=revision_note or f"Replace content from {document.filename}",
            created_by=created_by,
        )
        # Replace means this document supersedes prior source references for this page.
        page.source_documents = [current_doc_ref]
    elif action in {"append", "replace"} and page is None:
        raise BadRequestError(
            f"Cannot {action}: page '{normalized['page_title']}' was not found in category '{category.name}'"
        )
    else:
        desired_title = normalized["page_title"]
        if action == "create_new":
            desired_title = await _next_available_title(db, tenant_id, desired_title)
        page = await create_page(
            db,
            tenant_id=tenant_id,
            title=desired_title,
            markdown_content=content,
            category_id=category.id,
        )
        _append_source_document(page, document.id)

    if action == "append":
        _append_source_document(page, document.id)

    for old_doc_ref in replaced_source_documents:
        if old_doc_ref == current_doc_ref:
            continue
        if await _document_is_referenced_elsewhere(
            db,
            tenant_id=tenant_id,
            document_ref=old_doc_ref,
            excluding_page_id=page.id,
        ):
            continue
        try:
            await _remove_document_vectors(db, tenant_id, uuid.UUID(old_doc_ref))
        except (ValueError, TypeError):
            continue

    await db.flush()
    return [page]


async def generate_wiki_from_content(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    content: str,
    document_id: uuid.UUID,
    preferred_language: str | None = None,
) -> list[WikiPage]:
    """Use LLM to organize content into wiki pages."""
    result = await generate_text(
        with_output_language(WIKI_ORGANIZE_PROMPT, preferred_language),
        f"Organize this content into wiki pages:\n\n{content[:15000]}",
    )

    try:
        data = json.loads(_strip_json_fences(result))
    except (json.JSONDecodeError, IndexError):
        page = await create_page(db, tenant_id, "Imported Content", content)
        _append_source_document(page, document_id)
        await db.flush()
        return [page]

    pages = []
    for cat_data in data.get("categories", []):
        category = await create_category(db, tenant_id, cat_data["name"])
        for page_data in cat_data.get("pages", []):
            page = await create_page(
                db, tenant_id, page_data["title"], page_data["content"], category.id
            )
            _append_source_document(page, document_id)
            pages.append(page)

    await db.flush()
    return pages
