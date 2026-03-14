import uuid
from pydantic import BaseModel


class SearchResult(BaseModel):
    source_type: str
    source_id: uuid.UUID
    title: str
    snippet: str
    score: float = 0.0


class SearchResponse(BaseModel):
    results: list[SearchResult]
