import uuid
from datetime import datetime
from pydantic import BaseModel


class MeetingUploadResponse(BaseModel):
    id: uuid.UUID
    title: str
    status: str


class MeetingResponse(BaseModel):
    id: uuid.UUID
    title: str
    duration_seconds: float | None
    status: str
    meeting_date: datetime | None
    participants: list | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MeetingListResponse(BaseModel):
    items: list[MeetingResponse]
    total: int
    page: int
    page_size: int


class TranscriptSegment(BaseModel):
    speaker: str
    start: float
    end: float
    text: str


class TranscriptResponse(BaseModel):
    meeting_id: uuid.UUID
    full_text: str
    segments: list[TranscriptSegment] | None
    summary: str | None
    action_items: list | None

    model_config = {"from_attributes": True}
