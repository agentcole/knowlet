import re
import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk, DocumentStatus
from app.models.meeting import MeetingRecording, MeetingTranscript
from app.models.wiki import WikiPage
from app.services.wiki_service import extract_indexable_wiki_text
from app.services.vector_service import embed_query, get_tenant_store


def _query_terms(query: str) -> list[str]:
    terms = re.findall(r"[a-zA-Z0-9]{3,}", query.lower())
    deduped: list[str] = []
    for term in terms:
        if term not in deduped:
            deduped.append(term)
    return deduped[:10]


def _match_score(text: str, terms: list[str], base: float) -> float:
    if not terms:
        return base
    haystack = text.lower()
    matches = sum(1 for term in terms if term in haystack)
    return base + (min(matches, 6) * 0.06)


def _clean_snippet(text: str, max_len: int = 240) -> str:
    compact = re.sub(r"\s+", " ", (text or "")).strip()
    if len(compact) <= max_len:
        return compact
    return compact[: max_len - 1].rstrip() + "…"


def _wiki_text(page: WikiPage) -> str:
    return extract_indexable_wiki_text(page.markdown_content or "")


async def search_all(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    query: str,
    limit: int = 30,
) -> list[dict]:
    terms = _query_terms(query)
    ranked: list[dict] = []
    seen: set[str] = set()

    # Vector search (documents + wiki pages)
    vector_results: list[dict] = []
    try:
        query_vector = await embed_query(query)
        store = get_tenant_store(tenant_id)
        vector_results = store.query(query_vector, top_k=10)
    except Exception:
        vector_results = []

    vector_chunk_ids: list[uuid.UUID] = []
    vector_wiki_page_ids: list[uuid.UUID] = []
    parsed_vector_results: list[dict] = []
    for result in vector_results:
        metadata = result.get("metadata") or {}
        source_type = metadata.get("type")
        source_id = str(result.get("id") or "")

        if source_type == "wiki_page":
            page_id_raw = metadata.get("wiki_page_id")
            try:
                page_id = uuid.UUID(str(page_id_raw))
            except (ValueError, TypeError):
                continue
            vector_wiki_page_ids.append(page_id)
            parsed_vector_results.append(
                {
                    "kind": "wiki_page",
                    "page_id": str(page_id),
                    "score": float(result.get("score", 0.0)),
                    "metadata": metadata,
                }
            )
            continue

        # Backward-compatible default: vector ids without type metadata are treated as chunk ids.
        if source_type in (None, "", "document_chunk"):
            try:
                chunk_uuid = uuid.UUID(source_id)
            except (ValueError, TypeError):
                continue
            vector_chunk_ids.append(chunk_uuid)
            parsed_vector_results.append(
                {
                    "kind": "document_chunk",
                    "chunk_id": str(chunk_uuid),
                    "score": float(result.get("score", 0.0)),
                    "metadata": metadata,
                }
            )

    vector_chunks: dict[str, tuple[DocumentChunk, str, uuid.UUID]] = {}
    if vector_chunk_ids:
        chunk_rows = await db.execute(
            select(DocumentChunk, Document.filename, Document.id)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.id.in_(vector_chunk_ids),
                DocumentChunk.tenant_id == tenant_id,
                DocumentChunk.vector_indexed.is_(True),
                Document.tenant_id == tenant_id,
                Document.status == DocumentStatus.PROCESSED,
            )
        )
        for chunk, filename, doc_id in chunk_rows.all():
            vector_chunks[str(chunk.id)] = (chunk, filename, doc_id)

    vector_wiki_pages: dict[str, WikiPage] = {}
    if vector_wiki_page_ids:
        page_rows = await db.execute(
            select(WikiPage).where(
                WikiPage.id.in_(vector_wiki_page_ids),
                WikiPage.tenant_id == tenant_id,
            )
        )
        for page in page_rows.scalars().all():
            vector_wiki_pages[str(page.id)] = page

    for vr in parsed_vector_results:
        if vr["kind"] == "document_chunk":
            chunk_id = vr["chunk_id"]
            chunk_match = vector_chunks.get(chunk_id)
            if not chunk_match:
                continue
            chunk, filename, _doc_id = chunk_match
            key = f"document_chunk:{chunk_id}"
            if key in seen:
                continue
            seen.add(key)
            ranked.append(
                {
                    "source_type": "document_chunk",
                    "source_id": uuid.UUID(chunk_id),
                    "title": filename,
                    "snippet": _clean_snippet(chunk.content),
                    "score": vr["score"] * 0.7,
                }
            )
            continue

        if vr["kind"] == "wiki_page":
            page_id = vr["page_id"]
            page = vector_wiki_pages.get(page_id)
            if not page:
                continue
            key = f"wiki_page:{page_id}"
            if key in seen:
                continue
            seen.add(key)
            metadata = vr.get("metadata") or {}
            ranked.append(
                {
                    "source_type": "wiki_page",
                    "source_id": uuid.UUID(page_id),
                    "title": str(metadata.get("title") or page.title),
                    "snippet": _clean_snippet(str(metadata.get("content") or _wiki_text(page))),
                    "score": vr["score"] * 0.7,
                }
            )

    # Keyword search: wiki pages
    page_matchers = [
        (WikiPage.title.ilike(f"%{query}%"))
        | (WikiPage.markdown_content.ilike(f"%{query}%"))
    ]
    for term in terms:
        page_matchers.append(
            (WikiPage.title.ilike(f"%{term}%"))
            | (WikiPage.markdown_content.ilike(f"%{term}%"))
        )
    page_rows = await db.execute(
        select(WikiPage)
        .where(WikiPage.tenant_id == tenant_id, or_(*page_matchers))
        .limit(20)
    )
    for page in page_rows.scalars().all():
        wiki_text = _wiki_text(page)
        key = f"wiki_page:{page.id}"
        if key in seen:
            continue
        seen.add(key)
        ranked.append(
            {
                "source_type": "wiki_page",
                "source_id": page.id,
                "title": page.title,
                "snippet": _clean_snippet(wiki_text),
                "score": _match_score(
                    f"{page.title}\n{wiki_text[:2000]}",
                    terms,
                    0.32,
                ),
            }
        )

    # Keyword search: documents
    doc_matchers = [
        (Document.filename.ilike(f"%{query}%"))
        | (Document.markdown_content.ilike(f"%{query}%"))
    ]
    for term in terms:
        doc_matchers.append(
            (Document.filename.ilike(f"%{term}%"))
            | (Document.markdown_content.ilike(f"%{term}%"))
        )
    doc_rows = await db.execute(
        select(Document)
        .where(
            Document.tenant_id == tenant_id,
            Document.status == DocumentStatus.PROCESSED,
            or_(*doc_matchers),
        )
        .limit(20)
    )
    for doc in doc_rows.scalars().all():
        key = f"document:{doc.id}"
        if key in seen:
            continue
        seen.add(key)
        ranked.append(
            {
                "source_type": "document",
                "source_id": doc.id,
                "title": doc.filename,
                "snippet": _clean_snippet(doc.markdown_content or ""),
                "score": _match_score(
                    f"{doc.filename}\n{(doc.markdown_content or '')[:2000]}",
                    terms,
                    0.3,
                ),
            }
        )

    # Keyword search: meetings
    meeting_matchers = [
        (MeetingRecording.title.ilike(f"%{query}%"))
        | (MeetingTranscript.full_text.ilike(f"%{query}%"))
        | (MeetingTranscript.summary.ilike(f"%{query}%"))
    ]
    for term in terms:
        meeting_matchers.append(
            (MeetingRecording.title.ilike(f"%{term}%"))
            | (MeetingTranscript.full_text.ilike(f"%{term}%"))
            | (MeetingTranscript.summary.ilike(f"%{term}%"))
        )
    meeting_rows = await db.execute(
        select(MeetingRecording, MeetingTranscript)
        .join(MeetingTranscript, MeetingTranscript.meeting_id == MeetingRecording.id)
        .where(
            MeetingRecording.tenant_id == tenant_id,
            MeetingTranscript.tenant_id == tenant_id,
            or_(*meeting_matchers),
        )
        .limit(20)
    )
    for meeting, transcript in meeting_rows.all():
        key = f"meeting:{meeting.id}"
        if key in seen:
            continue
        seen.add(key)
        text_blob = transcript.summary or transcript.full_text or ""
        ranked.append(
            {
                "source_type": "meeting",
                "source_id": meeting.id,
                "title": meeting.title,
                "snippet": _clean_snippet(text_blob),
                "score": _match_score(
                    f"{meeting.title}\n{text_blob[:2000]}",
                    terms,
                    0.28,
                ),
            }
        )

    ranked.sort(key=lambda item: item.get("score", 0.0), reverse=True)
    return ranked[:limit]
