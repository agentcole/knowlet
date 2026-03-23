import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin


class WikiCategory(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "wiki_categories"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wiki_categories.id", ondelete="SET NULL"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    parent = relationship("WikiCategory", remote_side="WikiCategory.id", backref="children")
    pages = relationship("WikiPage", back_populates="category", cascade="all, delete-orphan")


class WikiPage(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "wiki_pages"

    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wiki_categories.id", ondelete="SET NULL"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    markdown_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source_documents: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=list)
    source_meetings: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=list)

    category = relationship("WikiCategory", back_populates="pages")
    revisions = relationship(
        "WikiPageRevision",
        back_populates="page",
        cascade="all, delete-orphan",
        order_by="WikiPageRevision.created_at.desc()",
    )


class WikiPageRevision(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "wiki_page_revisions"

    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wiki_pages.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    markdown_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    page = relationship("WikiPage", back_populates="revisions")


class WikiAsset(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "wiki_assets"

    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
