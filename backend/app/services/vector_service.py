import uuid
import shutil
from pathlib import Path

import numpy as np
from langchain_voyageai import VoyageAIEmbeddings

from app.config import settings

_embeddings: VoyageAIEmbeddings | None = None


def get_embeddings() -> VoyageAIEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = VoyageAIEmbeddings(
            model="voyage-3-large",
            voyage_api_key=settings.VOYAGE_API_KEY,
        )
    return _embeddings


def _get_collection_path(tenant_id: uuid.UUID) -> str:
    path = Path(settings.STORAGE_ROOT) / str(tenant_id) / "vectors"
    path.mkdir(parents=True, exist_ok=True)
    return str(path / "index")


def reset_tenant_store(tenant_id: uuid.UUID) -> None:
    key = str(tenant_id)
    _stores.pop(key, None)
    vector_dir = Path(settings.STORAGE_ROOT) / str(tenant_id) / "vectors"
    if vector_dir.exists():
        shutil.rmtree(vector_dir, ignore_errors=True)


async def embed_texts(texts: list[str]) -> list[list[float]]:
    embeddings = get_embeddings()
    return await embeddings.aembed_documents(texts)


async def embed_query(text: str) -> list[float]:
    embeddings = get_embeddings()
    return await embeddings.aembed_query(text)


class TenantVectorStore:
    def __init__(self, tenant_id: uuid.UUID):
        self.tenant_id = tenant_id
        self.path = _get_collection_path(tenant_id)
        self._index = None
        self._ids: list[str] = []
        self._vectors: list[list[float]] = []
        self._metadata: list[dict] = []
        self._load()

    def _load(self):
        try:
            import zvec
            self._index = zvec.Index(dim=1024, path=self.path)
        except Exception:
            self._index = None

    def insert(self, chunk_id: str, vector: list[float], metadata: dict | None = None):
        if self._index is not None:
            try:
                self._index.add(
                    ids=[chunk_id],
                    vectors=[vector],
                    metadata=[metadata or {}],
                )
                return
            except Exception:
                pass
        self._ids.append(chunk_id)
        self._vectors.append(vector)
        self._metadata.append(metadata or {})

    def query(self, vector: list[float], top_k: int = 10) -> list[dict]:
        if self._index is not None:
            try:
                results = self._index.search(vector=vector, k=top_k)
                return [
                    {"id": r.id, "score": r.score, "metadata": r.metadata}
                    for r in results
                ]
            except Exception:
                pass

        if not self._vectors:
            return []
        query_vec = np.array(vector)
        scores = []
        for i, v in enumerate(self._vectors):
            vec = np.array(v)
            cos_sim = np.dot(query_vec, vec) / (np.linalg.norm(query_vec) * np.linalg.norm(vec) + 1e-10)
            scores.append((i, float(cos_sim)))
        scores.sort(key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in scores[:top_k]:
            results.append({
                "id": self._ids[idx],
                "score": score,
                "metadata": self._metadata[idx],
            })
        return results

    def delete(self, chunk_id: str):
        if self._index is not None:
            try:
                self._index.delete(ids=[chunk_id])
                return
            except Exception:
                pass
        if chunk_id in self._ids:
            idx = self._ids.index(chunk_id)
            self._ids.pop(idx)
            self._vectors.pop(idx)
            self._metadata.pop(idx)


_stores: dict[str, TenantVectorStore] = {}


def get_tenant_store(tenant_id: uuid.UUID) -> TenantVectorStore:
    key = str(tenant_id)
    if key not in _stores:
        _stores[key] = TenantVectorStore(tenant_id)
    return _stores[key]
