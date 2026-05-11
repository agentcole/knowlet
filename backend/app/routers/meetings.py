import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.database import get_db
from app.dependencies import get_current_user, get_tenant_id, get_tenant_membership
from app.models.tenant_membership import TenantMembership, TenantRole
from app.models.user import User
from app.schemas.meeting import (
    MeetingListResponse,
    MeetingResponse,
    MeetingUploadResponse,
    TranscriptResponse,
)
from app.services import meeting_service

router = APIRouter(prefix="/api/v1/meetings", tags=["meetings"])


@router.post("/upload", response_model=MeetingUploadResponse, status_code=202)
async def upload_meeting(
    file: UploadFile = File(...),
    title: str = Form(...),
    meeting_date: str | None = Form(None),
    language: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    file_data = await file.read()
    parsed_date = datetime.fromisoformat(meeting_date) if meeting_date else None

    meeting = await meeting_service.upload_meeting(
        db,
        tenant_id,
        current_user.id,
        title,
        file_data,
        file.filename or "recording",
        parsed_date,
        language or current_user.default_language,
    )

    try:
        from app.workers.meeting_tasks import process_meeting
        process_meeting.delay(str(meeting.id), str(tenant_id))
    except Exception:
        pass

    return MeetingUploadResponse(
        id=meeting.id,
        title=meeting.title,
        status=meeting.status.value,
        language=meeting.language,
    )


@router.get("/", response_model=MeetingListResponse)
async def list_meetings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    meetings, total = await meeting_service.list_meetings(db, tenant_id, page, page_size)
    return MeetingListResponse(
        items=[MeetingResponse.model_validate(m) for m in meetings],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    meeting = await meeting_service.get_meeting(db, tenant_id, meeting_id)
    return MeetingResponse.model_validate(meeting)


@router.delete("/{meeting_id}", status_code=204)
async def delete_meeting(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    membership: TenantMembership = Depends(get_tenant_membership),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    meeting = await meeting_service.get_meeting(db, tenant_id, meeting_id)
    can_delete = (
        meeting.uploaded_by == current_user.id
        or membership.role in (TenantRole.OWNER, TenantRole.ADMIN)
    )
    if not can_delete:
        raise ForbiddenError("Only the uploader or tenant admins can delete meetings")
    await meeting_service.delete_meeting(db, tenant_id, meeting_id)


@router.get("/{meeting_id}/transcript", response_model=TranscriptResponse)
async def get_transcript(
    meeting_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    transcript = await meeting_service.get_transcript(db, tenant_id, meeting_id)
    return TranscriptResponse.model_validate(transcript)


@router.get("/{meeting_id}/summary")
async def get_summary(
    meeting_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    transcript = await meeting_service.get_transcript(db, tenant_id, meeting_id)
    return {
        "summary": transcript.summary,
        "action_items": transcript.action_items,
    }
