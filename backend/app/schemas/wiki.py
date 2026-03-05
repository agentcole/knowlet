import uuid
from datetime import datetime
from pydantic import BaseModel


class WikiCategoryCreate(BaseModel):
    name: str
    parent_id: uuid.UUID | None = None
    sort_order: int = 0


class WikiCategoryUpdate(BaseModel):
    name: str | None = None
    parent_id: uuid.UUID | None = None
    sort_order: int | None = None


class WikiCategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    parent_id: uuid.UUID | None
    sort_order: int

    model_config = {"from_attributes": True}


class WikiPageCreate(BaseModel):
    title: str
    category_id: uuid.UUID | None = None
    sort_order: int | None = None
    markdown_content: str = ""


class WikiPageUpdate(BaseModel):
    title: str | None = None
    category_id: uuid.UUID | None = None
    sort_order: int | None = None
    markdown_content: str | None = None
    change_note: str | None = None


class WikiPageResponse(BaseModel):
    id: uuid.UUID
    title: str
    slug: str
    category_id: uuid.UUID | None
    sort_order: int
    markdown_content: str
    version: int
    source_documents: list | None
    source_meetings: list | None

    model_config = {"from_attributes": True}


class WikiPageRevisionResponse(BaseModel):
    id: uuid.UUID
    page_id: uuid.UUID
    version: int
    title: str
    markdown_content: str
    change_note: str | None
    created_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class WikiTreeCategory(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    sort_order: int
    children: list["WikiTreeCategory"]
    pages: list[WikiPageResponse]


class WikiTreeResponse(BaseModel):
    categories: list[WikiTreeCategory]
    uncategorized_pages: list[WikiPageResponse]
