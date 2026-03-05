import uuid
from datetime import datetime
from pydantic import AliasChoices, BaseModel, Field


class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    file_type: str
    status: str
    metadata: dict | None = Field(
        default=None,
        validation_alias=AliasChoices("doc_metadata", "metadata"),
    )
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int


class DocumentChunkResponse(BaseModel):
    id: uuid.UUID
    chunk_index: int
    content: str
    token_count: int
    metadata: dict | None = Field(
        default=None,
        validation_alias=AliasChoices("chunk_metadata", "metadata"),
    )

    model_config = {"from_attributes": True, "populate_by_name": True}


class WikiPlacementResponse(BaseModel):
    category_name: str
    page_title: str
    action: str
    reasoning: str | None = None
    confidence: float | None = None


class DocumentWikiWorkflowResponse(BaseModel):
    state: str
    language: str | None = None
    suggestion: WikiPlacementResponse | None = None
    placement: WikiPlacementResponse | None = None
    approved_by: uuid.UUID | None = None
    approved_at: datetime | None = None
    published_page_ids: list[uuid.UUID] | None = None
    revision_note: str | None = None
    error: str | None = None


class WikiPlacementInput(BaseModel):
    category_name: str
    page_title: str
    action: str = "create_new"


class DocumentWikiApprovalRequest(BaseModel):
    placement: WikiPlacementInput | None = None
    revision_note: str | None = None
