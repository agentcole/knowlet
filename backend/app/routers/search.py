import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_tenant_id
from app.schemas.search import SearchResponse, SearchResult
from app.services.search_service import search_all


router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=2),
    limit: int = Query(30, ge=1, le=100),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    results = await search_all(db, tenant_id, q, limit)
    return SearchResponse(results=[SearchResult(**r) for r in results])
