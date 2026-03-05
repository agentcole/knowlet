import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, get_db
from app.dependencies import get_current_user, get_tenant_id
from app.models.user import User
from app.schemas.chat import (
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    SendMessageRequest,
)
from app.services import chat_service

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("/sessions", response_model=ChatSessionResponse)
async def create_session(
    body: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    session = await chat_service.create_session(
        db, tenant_id, current_user.id, body.title
    )
    return ChatSessionResponse.model_validate(session)


@router.get("/sessions", response_model=list[ChatSessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    sessions = await chat_service.list_sessions(db, tenant_id, current_user.id)
    return [ChatSessionResponse.model_validate(s) for s in sessions]


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_session(
    session_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    session = await chat_service.get_session(db, tenant_id, session_id)
    return ChatSessionResponse.model_validate(session)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
async def get_messages(
    session_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    session = await chat_service.get_session(db, tenant_id, session_id)
    return [ChatMessageResponse.model_validate(m) for m in session.messages]


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    await chat_service.delete_session(db, tenant_id, session_id)


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: uuid.UUID,
    body: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
):
    def _format_sse_data(data: str) -> str:
        normalized = (data or "").replace("\r", "").replace("\n", "\ndata: ")
        return f"data: {normalized}\n\n"

    async def event_stream():
        async with async_session_factory() as db:
            try:
                async for chunk in chat_service.send_message(
                    db,
                    tenant_id,
                    session_id,
                    body.content,
                    current_user.default_language,
                ):
                    yield _format_sse_data(chunk)
            except Exception:
                await db.rollback()
                yield _format_sse_data(
                    "I ran into an error while sending this message. Please try again."
                )
            finally:
                yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
