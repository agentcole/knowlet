import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.language import normalize_language
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.models.wiki import WikiPage
from app.services.wiki_service import suggest_wiki_placement
from app.services.vector_service import embed_texts, get_tenant_store, reset_tenant_store
from app.services.wiki_workflow import get_workflow, set_workflow
from app.workers.celery_app import celery_app


def _get_session_factory():
    engine = create_async_engine(settings.DATABASE_URL)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _regenerate_wiki(tenant_id: str):
    session_factory = _get_session_factory()
    tid = uuid.UUID(tenant_id)

    async with session_factory() as db:
        result = await db.execute(
            select(Document).where(
                Document.tenant_id == tid,
                Document.status == DocumentStatus.PROCESSED,
            )
        )
        documents = result.scalars().all()

        for doc in documents:
            if doc.markdown_content:
                try:
                    workflow = get_workflow(doc.doc_metadata)
                    if workflow.get("state") == "published":
                        continue

                    language_code = normalize_language(workflow.get("language"))
                    suggestion = await suggest_wiki_placement(
                        db,
                        tenant_id=tid,
                        filename=doc.filename,
                        content=doc.markdown_content,
                        preferred_language=language_code,
                    )
                    workflow.update(
                        {
                            "state": "pending_approval",
                            "suggestion": suggestion,
                            "placement": None,
                            "approved_by": None,
                            "approved_at": None,
                            "published_page_ids": None,
                            "language": language_code,
                            "error": None,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    doc.doc_metadata = set_workflow(doc.doc_metadata, workflow)
                except Exception:
                    continue

        await db.commit()


@celery_app.task(name="regenerate_wiki", bind=True, max_retries=1)
def regenerate_wiki(self, tenant_id: str):
    try:
        asyncio.run(_regenerate_wiki(tenant_id))
    except Exception as exc:
        self.retry(exc=exc, countdown=120)


async def _reindex_wiki_vectors(tenant_id: str):
    session_factory = _get_session_factory()
    tid = uuid.UUID(tenant_id)
    reset_tenant_store(tid)

    async with session_factory() as db:
        store = get_tenant_store(tid)

        chunk_result = await db.execute(
            select(DocumentChunk, Document.filename)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.tenant_id == tid,
                Document.tenant_id == tid,
                Document.status == DocumentStatus.PROCESSED,
            )
            .order_by(DocumentChunk.chunk_index.asc())
        )
        chunk_rows = list(chunk_result.all())

        for chunk, _ in chunk_rows:
            chunk.vector_indexed = False

        if chunk_rows:
            chunk_texts = [chunk.content for chunk, _ in chunk_rows]
            chunk_vectors = await embed_texts(chunk_texts)
            for (chunk, filename), vector in zip(chunk_rows, chunk_vectors):
                store.insert(
                    str(chunk.id),
                    vector,
                    {
                        "type": "document_chunk",
                        "document_id": str(chunk.document_id),
                        "chunk_index": chunk.chunk_index,
                        "title": filename,
                        "content": chunk.content[:500],
                    },
                )
                chunk.vector_indexed = True

        wiki_rows = await db.execute(
            select(WikiPage).where(
                WikiPage.tenant_id == tid,
            )
        )
        pages = list(wiki_rows.scalars().all())

        wiki_chunks: list[tuple[str, str, dict]] = []
        for page in pages:
            content = (page.markdown_content or "").strip()
            if not content:
                continue

            try:
                from langchain_text_splitters import RecursiveCharacterTextSplitter

                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=700,
                    chunk_overlap=80,
                    separators=["\n## ", "\n### ", "\n\n", "\n", " "],
                )
                page_chunks = splitter.split_text(content)
            except Exception:
                page_chunks = [content[i : i + 700] for i in range(0, len(content), 700)]

            for idx, chunk_text in enumerate(page_chunks):
                vector_id = str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"{tenant_id}:wiki:{page.id}:{idx}",
                    )
                )
                wiki_chunks.append(
                    (
                        vector_id,
                        chunk_text,
                        {
                            "type": "wiki_page",
                            "wiki_page_id": str(page.id),
                            "title": page.title,
                            "content": chunk_text[:500],
                        },
                    )
                )

        if wiki_chunks:
            wiki_vectors = await embed_texts([chunk for _, chunk, _ in wiki_chunks])
            for (vector_id, _, metadata), vector in zip(wiki_chunks, wiki_vectors):
                store.insert(vector_id, vector, metadata)

        await db.commit()


@celery_app.task(name="reindex_wiki_vectors", bind=True, max_retries=1)
def reindex_wiki_vectors(self, tenant_id: str):
    try:
        asyncio.run(_reindex_wiki_vectors(tenant_id))
    except Exception as exc:
        self.retry(exc=exc, countdown=120)
