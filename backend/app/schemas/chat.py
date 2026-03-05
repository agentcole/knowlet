import uuid
from datetime import datetime
from pydantic import BaseModel


class ChatSessionCreate(BaseModel):
    title: str = "New Chat"


class ChatSessionResponse(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SourceReference(BaseModel):
    wiki_page_id: uuid.UUID | None = None
    chunk_id: uuid.UUID | None = None
    score: float = 0.0
    title: str = ""
    snippet: str = ""


class ChatMessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    sources: list[SourceReference] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SendMessageRequest(BaseModel):
    content: str
