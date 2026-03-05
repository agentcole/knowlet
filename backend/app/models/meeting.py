import uuid
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin


class MeetingStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    TRANSCRIBING = "transcribing"
    SUMMARIZING = "summarizing"
    PROCESSED = "processed"
    FAILED = "failed"


class MeetingRecording(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "meeting_recordings"

    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[MeetingStatus] = mapped_column(
        Enum(
            MeetingStatus,
            values_callable=lambda statuses: [status.value for status in statuses],
            name="meetingstatus",
        ),
        default=MeetingStatus.UPLOADED,
        nullable=False,
    )
    meeting_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    participants: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=list)

    transcript = relationship(
        "MeetingTranscript",
        back_populates="meeting",
        uselist=False,
        cascade="all, delete-orphan",
    )


class MeetingTranscript(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "meeting_transcripts"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meeting_recordings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    full_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    segments: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=list)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_items: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=list)
    wiki_pages_updated: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=list)

    meeting = relationship("MeetingRecording", back_populates="transcript")
