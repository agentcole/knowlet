import uuid
import re

from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.models.wiki import WikiPage
from app.services.llm_service import CHAT_SYSTEM_PROMPT, stream_text, with_output_language
from app.services.vector_service import embed_query, get_tenant_store


async def create_session(
    db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID, title: str = "New Chat"
) -> ChatSession:
    session = ChatSession(tenant_id=tenant_id, user_id=user_id, title=title)
    db.add(session)
    await db.flush()
    return session


async def get_session(
    db: AsyncSession, tenant_id: uuid.UUID, session_id: uuid.UUID
) -> ChatSession:
    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(ChatSession.id == session_id, ChatSession.tenant_id == tenant_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise NotFoundError("Chat session not found")
    return session


async def list_sessions(
    db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> list[ChatSession]:
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.tenant_id == tenant_id, ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
    )
    return list(result.scalars().all())


async def delete_session(
    db: AsyncSession, tenant_id: uuid.UUID, session_id: uuid.UUID
) -> None:
    session = await get_session(db, tenant_id, session_id)
    await db.delete(session)
    await db.flush()


def _query_terms(query: str) -> list[str]:
    terms = re.findall(r"[a-zA-Z0-9]{3,}", query.lower())
    deduped: list[str] = []
    for term in terms:
        if term not in deduped:
            deduped.append(term)
    return deduped[:8]


def _match_score(text: str, terms: list[str], base: float) -> float:
    if not terms:
        return base
    haystack = text.lower()
    matches = sum(1 for term in terms if term in haystack)
    return base + (min(matches, 5) * 0.08)


async def _get_context(
    db: AsyncSession, tenant_id: uuid.UUID, query: str
) -> tuple[str, list[dict]]:
    """Hybrid search: vector + keyword, merge and rank."""
    terms = _query_terms(query)

    # Vector search
    try:
        query_vector = await embed_query(query)
        store = get_tenant_store(tenant_id)
        vector_results = store.query(query_vector, top_k=10)
    except Exception:
        vector_results = []

    # Validate vector hits against current DB rows so deleted chunks/pages are ignored.
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

    vector_chunks: dict[str, tuple[DocumentChunk, str]] = {}
    if vector_chunk_ids:
        vector_rows = await db.execute(
            select(DocumentChunk, Document.filename)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.id.in_(vector_chunk_ids),
                DocumentChunk.tenant_id == tenant_id,
                DocumentChunk.vector_indexed.is_(True),
                Document.tenant_id == tenant_id,
                Document.status == DocumentStatus.PROCESSED,
            )
        )
        for chunk, filename in vector_rows.all():
            vector_chunks[str(chunk.id)] = (chunk, filename)

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

    # Wiki keyword search
    page_matchers = [
        (WikiPage.title.ilike(f"%{query}%")) | (WikiPage.markdown_content.ilike(f"%{query}%"))
    ]
    for term in terms:
        page_matchers.append(
            (WikiPage.title.ilike(f"%{term}%")) | (WikiPage.markdown_content.ilike(f"%{term}%"))
        )
    keyword_results = await db.execute(
        select(WikiPage)
        .where(
            WikiPage.tenant_id == tenant_id,
            or_(*page_matchers),
        )
        .limit(20)
    )
    keyword_pages = list(keyword_results.scalars().all())

    # Processed document chunk fallback (includes content not yet published to wiki)
    chunk_matchers = [DocumentChunk.content.ilike(f"%{query}%")]
    for term in terms:
        chunk_matchers.append(DocumentChunk.content.ilike(f"%{term}%"))
    chunk_results = await db.execute(
        select(DocumentChunk, Document.filename)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.tenant_id == tenant_id,
            DocumentChunk.vector_indexed.is_(True),
            Document.tenant_id == tenant_id,
            Document.status == DocumentStatus.PROCESSED,
            or_(*chunk_matchers),
        )
        .limit(30)
    )
    keyword_chunks = list(chunk_results.all())

    # Processed document body fallback
    doc_matchers = [Document.markdown_content.ilike(f"%{query}%")]
    for term in terms:
        doc_matchers.append(Document.markdown_content.ilike(f"%{term}%"))
    doc_results = await db.execute(
        select(Document)
        .where(
            Document.tenant_id == tenant_id,
            Document.status == DocumentStatus.PROCESSED,
            Document.markdown_content.is_not(None),
            or_(*doc_matchers),
            exists(
                select(DocumentChunk.id).where(
                    DocumentChunk.document_id == Document.id,
                    DocumentChunk.tenant_id == tenant_id,
                    DocumentChunk.vector_indexed.is_(True),
                )
            ),
        )
        .limit(10)
    )
    keyword_documents = list(doc_results.scalars().all())

    # Merge results
    seen_ids = set()
    ranked = []

    for vr in parsed_vector_results:
        if vr["kind"] == "document_chunk":
            chunk_id = vr["chunk_id"]
            chunk_match = vector_chunks.get(chunk_id)
            if chunk_match is None:
                continue
            chunk, filename = chunk_match
            source_key = f"chunk:{chunk_id}"
            if source_key in seen_ids:
                continue
            seen_ids.add(source_key)
            ranked.append(
                {
                    "chunk_id": chunk_id,
                    "title": filename,
                    "snippet": chunk.content[:500],
                    "score": vr["score"] * 0.7,
                }
            )
            continue

        if vr["kind"] == "wiki_page":
            page_id = vr["page_id"]
            page = vector_wiki_pages.get(page_id)
            if page is None:
                continue
            source_key = f"wiki:{page_id}"
            if source_key in seen_ids:
                continue
            seen_ids.add(source_key)
            metadata = vr.get("metadata") or {}
            ranked.append(
                {
                    "wiki_page_id": page_id,
                    "title": str(metadata.get("title") or page.title),
                    "snippet": str(metadata.get("content") or page.markdown_content[:500]),
                    "score": vr["score"] * 0.7,
                }
            )

    for page in keyword_pages:
        page_key = f"wiki:{page.id}"
        if page_key in seen_ids:
            continue
        seen_ids.add(page_key)
        ranked.append({
            "wiki_page_id": str(page.id),
            "title": page.title,
            "snippet": page.markdown_content[:500],
            "score": _match_score(
                f"{page.title}\n{page.markdown_content[:2000]}",
                terms,
                0.3,
            ),
        })

    for chunk, filename in keyword_chunks:
        chunk_key = f"chunk:{chunk.id}"
        if chunk_key in seen_ids:
            continue
        seen_ids.add(chunk_key)
        ranked.append({
            "chunk_id": str(chunk.id),
            "title": filename,
            "snippet": chunk.content[:500],
            "score": _match_score(chunk.content[:2000], terms, 0.35),
        })

    for document in keyword_documents:
        doc_key = f"doc:{document.id}"
        if doc_key in seen_ids:
            continue
        seen_ids.add(doc_key)
        snippet = (document.markdown_content or "")[:700]
        ranked.append({
            "document_id": str(document.id),
            "title": document.filename,
            "snippet": snippet,
            "score": _match_score(
                f"{document.filename}\n{(document.markdown_content or '')[:3000]}",
                terms,
                0.28,
            ),
        })

    # If semantic and keyword matching miss, still provide latest processed chunks
    # so the assistant can access indexed knowledge instead of returning empty context.
    if not ranked:
        recent_results = await db.execute(
            select(DocumentChunk, Document.filename)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.tenant_id == tenant_id,
                DocumentChunk.vector_indexed.is_(True),
                Document.tenant_id == tenant_id,
                Document.status == DocumentStatus.PROCESSED,
            )
            .order_by(DocumentChunk.updated_at.desc())
            .limit(5)
        )
        for chunk, filename in recent_results.all():
            ranked.append({
                "chunk_id": str(chunk.id),
                "title": filename,
                "snippet": chunk.content[:500],
                "score": 0.12,
            })

    ranked.sort(key=lambda x: x.get("score", 0), reverse=True)
    top_sources = ranked[:5]

    # Build context string
    context_parts = []
    for s in top_sources:
        if "snippet" in s:
            context_parts.append(f"### {s.get('title', 'Source')}\n{s['snippet']}")

    # Also fetch full wiki page content for keyword results
    for page in keyword_pages[:3]:
        context_parts.append(f"### {page.title}\n{page.markdown_content[:2000]}")

    context = "\n\n---\n\n".join(context_parts) if context_parts else "No relevant context found."
    return context, top_sources


async def send_message(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    content: str,
    language_code: str | None = None,
):
    """Send a message and stream the response."""
    session = await get_session(db, tenant_id, session_id)

    # Save user message
    user_msg = ChatMessage(
        session_id=session_id,
        role=MessageRole.USER,
        content=content,
    )
    db.add(user_msg)
    await db.flush()
    await db.commit()

    # Get RAG context
    context, sources = await _get_context(db, tenant_id, content)

    # Build history
    history = [
        {"role": msg.role.value, "content": msg.content}
        for msg in session.messages[-10:]
    ]

    system_prompt = with_output_language(
        CHAT_SYSTEM_PROMPT.replace("{context}", context),
        language_code,
    )

    # Stream response
    full_response = ""
    try:
        async for chunk in stream_text(system_prompt, content, history):
            full_response += chunk
            yield chunk
    except Exception:
        full_response = (
            "I ran into an error generating a response. Please try again in a moment."
        )
        sources = []
        yield full_response

    # Save assistant message
    if not full_response.strip():
        full_response = "No response generated."

    assistant_msg = ChatMessage(
        session_id=session_id,
        role=MessageRole.ASSISTANT,
        content=full_response,
        sources=sources,
    )
    db.add(assistant_msg)
    await db.flush()
    await db.commit()
