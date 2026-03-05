import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.language import normalize_language
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.services.wiki_service import suggest_wiki_placement
from app.services.vector_service import embed_texts, get_tenant_store
from app.services.wiki_workflow import get_workflow, set_workflow
from app.workers.celery_app import celery_app


def _get_session_factory():
    engine = create_async_engine(settings.DATABASE_URL)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _process_document(
    document_id: str,
    tenant_id: str,
    preferred_language: str | None = None,
):
    session_factory = _get_session_factory()
    tid = uuid.UUID(tenant_id)

    async with session_factory() as db:
        result = await db.execute(
            select(Document).where(Document.id == uuid.UUID(document_id))
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return

        existing_workflow = get_workflow(doc.doc_metadata)
        language_code = normalize_language(
            preferred_language or existing_workflow.get("language")
        )
        doc.status = DocumentStatus.PROCESSING
        workflow = existing_workflow
        workflow.update(
            {"state": "processing", "error": None, "language": language_code}
        )
        doc.doc_metadata = set_workflow(doc.doc_metadata, workflow)
        await db.commit()

        try:
            # Read file and convert with Docling
            from app.services.storage_service import storage
            file_data = await storage.read(doc.storage_path)

            markdown_content = ""
            text_extensions = {
                "txt",
                "md",
                "markdown",
                "csv",
                "json",
                "yaml",
                "yml",
                "log",
            }
            if doc.file_type.lower() in text_extensions:
                markdown_content = file_data.decode("utf-8", errors="replace")
            else:
                try:
                    from docling.document_converter import DocumentConverter
                    import tempfile
                    import os

                    with tempfile.NamedTemporaryFile(
                        suffix=f".{doc.file_type}", delete=False
                    ) as tmp:
                        tmp.write(file_data)
                        tmp_path = tmp.name

                    try:
                        converter = DocumentConverter()
                        docling_result = converter.convert(tmp_path)
                        markdown_content = docling_result.document.export_to_markdown()
                    finally:
                        os.unlink(tmp_path)
                except ImportError:
                    raise RuntimeError(
                        "Docling is required to process this file type"
                    ) from None

            if not markdown_content.strip():
                raise RuntimeError("No text content could be extracted from document")

            doc.markdown_content = markdown_content

            # Reprocessing: purge prior chunks + vectors for this document before rebuilding.
            existing_result = await db.execute(
                select(DocumentChunk).where(
                    DocumentChunk.document_id == doc.id,
                    DocumentChunk.tenant_id == tid,
                )
            )
            existing_chunks = list(existing_result.scalars().all())
            if existing_chunks:
                try:
                    store = get_tenant_store(tid)
                    for existing_chunk in existing_chunks:
                        store.delete(str(existing_chunk.id))
                        existing_chunk.vector_indexed = False
                except Exception:
                    pass

                for existing_chunk in existing_chunks:
                    await db.delete(existing_chunk)
                await db.flush()

            # Chunk the content
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=50,
                separators=["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " "],
            )
            chunks_text = splitter.split_text(markdown_content)

            chunk_objects = []
            for i, chunk_text in enumerate(chunks_text):
                chunk = DocumentChunk(
                    tenant_id=tid,
                    document_id=doc.id,
                    chunk_index=i,
                    content=chunk_text,
                    token_count=len(chunk_text.split()),
                )
                db.add(chunk)
                chunk_objects.append(chunk)

            await db.flush()

            # Embed chunks and index in vector store
            try:
                texts = [c.content for c in chunk_objects]
                vectors = await embed_texts(texts)
                store = get_tenant_store(tid)

                for chunk_obj, vector in zip(chunk_objects, vectors):
                    store.insert(
                        str(chunk_obj.id),
                        vector,
                        {
                            "document_id": str(doc.id),
                            "chunk_index": chunk_obj.chunk_index,
                            "content": chunk_obj.content[:500],
                            "language": language_code,
                        },
                    )
                    chunk_obj.vector_indexed = True
            except Exception:
                pass  # Vector indexing is non-critical

            suggestion = await suggest_wiki_placement(
                db,
                tenant_id=tid,
                filename=doc.filename,
                content=markdown_content,
                preferred_language=language_code,
            )

            workflow = get_workflow(doc.doc_metadata)
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
            doc.status = DocumentStatus.PROCESSED
            await db.commit()

        except Exception as e:
            doc.status = DocumentStatus.FAILED
            workflow = get_workflow(doc.doc_metadata)
            workflow.update(
                {
                    "state": "failed",
                    "language": language_code,
                    "error": str(e),
                }
            )
            doc.doc_metadata = set_workflow(doc.doc_metadata, workflow)
            await db.commit()


@celery_app.task(name="process_document", bind=True, max_retries=3)
def process_document(
    self,
    document_id: str,
    tenant_id: str,
    preferred_language: str | None = None,
):
    try:
        asyncio.run(_process_document(document_id, tenant_id, preferred_language))
    except Exception as exc:
        self.retry(exc=exc, countdown=60)
