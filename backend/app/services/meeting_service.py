import json
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.core.language import normalize_language
from app.models.meeting import MeetingRecording, MeetingStatus, MeetingTranscript
from app.models.wiki import WikiPage
from app.services.storage_service import storage


async def upload_meeting(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str,
    file_data: bytes,
    filename: str,
    meeting_date: datetime | None = None,
    language: str | None = None,
) -> MeetingRecording:
    storage_path = await storage.save(tenant_id, "meetings", filename, file_data)

    meeting = MeetingRecording(
        tenant_id=tenant_id,
        uploaded_by=user_id,
        title=title,
        storage_path=storage_path,
        status=MeetingStatus.UPLOADED,
        meeting_date=meeting_date,
        language=normalize_language(language),
    )
    db.add(meeting)
    await db.flush()
    return meeting


async def get_meeting(
    db: AsyncSession, tenant_id: uuid.UUID, meeting_id: uuid.UUID
) -> MeetingRecording:
    result = await db.execute(
        select(MeetingRecording).where(
            MeetingRecording.id == meeting_id,
            MeetingRecording.tenant_id == tenant_id,
        )
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise NotFoundError("Meeting not found")
    return meeting


async def delete_meeting(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    meeting_id: uuid.UUID,
) -> None:
    meeting = await get_meeting(db, tenant_id, meeting_id)
    if meeting.status in (MeetingStatus.TRANSCRIBING, MeetingStatus.SUMMARIZING):
        raise BadRequestError("Cannot delete a meeting while it is being processed")

    await storage.delete(meeting.storage_path)

    meeting_ref = str(meeting.id)
    page_result = await db.execute(
        select(WikiPage).where(
            WikiPage.tenant_id == tenant_id,
            WikiPage.source_meetings.contains([meeting_ref]),
        )
    )
    for page in page_result.scalars().all():
        page.source_meetings = [
            ref for ref in (page.source_meetings or []) if ref != meeting_ref
        ]

    await db.delete(meeting)
    await db.flush()


async def list_meetings(
    db: AsyncSession, tenant_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[MeetingRecording], int]:
    query = (
        select(MeetingRecording)
        .where(MeetingRecording.tenant_id == tenant_id)
        .order_by(MeetingRecording.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    meetings = list(result.scalars().all())

    count_result = await db.execute(
        select(func.count()).select_from(MeetingRecording).where(MeetingRecording.tenant_id == tenant_id)
    )
    total = count_result.scalar() or 0
    return meetings, total


async def get_transcript(
    db: AsyncSession, tenant_id: uuid.UUID, meeting_id: uuid.UUID
) -> MeetingTranscript:
    result = await db.execute(
        select(MeetingTranscript).where(
            MeetingTranscript.meeting_id == meeting_id,
            MeetingTranscript.tenant_id == tenant_id,
        )
    )
    transcript = result.scalar_one_or_none()
    if not transcript:
        raise NotFoundError("Transcript not found")
    return transcript


async def save_transcript(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    meeting_id: uuid.UUID,
    full_text: str,
    segments: list[dict],
    summary: str | None = None,
    action_items: list | None = None,
) -> MeetingTranscript:
    transcript = MeetingTranscript(
        tenant_id=tenant_id,
        meeting_id=meeting_id,
        full_text=full_text,
        segments=segments,
        summary=summary,
        action_items=action_items or [],
    )
    db.add(transcript)
    await db.flush()
    return transcript
