import os
import uuid
from pathlib import Path

import aiofiles

from app.config import settings


class LocalStorageBackend:
    def __init__(self, root: str | None = None):
        self.root = Path(root or settings.STORAGE_ROOT)

    def _tenant_path(self, tenant_id: uuid.UUID) -> Path:
        return self.root / str(tenant_id)

    async def save(
        self, tenant_id: uuid.UUID, category: str, filename: str, data: bytes
    ) -> str:
        dir_path = self._tenant_path(tenant_id) / category
        dir_path.mkdir(parents=True, exist_ok=True)

        unique_name = f"{uuid.uuid4().hex}_{filename}"
        file_path = dir_path / unique_name
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(data)
        return str(file_path)

    async def read(self, path: str) -> bytes:
        async with aiofiles.open(path, "rb") as f:
            return await f.read()

    async def delete(self, path: str) -> None:
        p = Path(path)
        if p.exists():
            p.unlink()

    def list_files(self, tenant_id: uuid.UUID, category: str) -> list[str]:
        dir_path = self._tenant_path(tenant_id) / category
        if not dir_path.exists():
            return []
        return [str(f) for f in dir_path.iterdir() if f.is_file()]

    async def save_text(
        self, tenant_id: uuid.UUID, category: str, filename: str, text: str
    ) -> str:
        dir_path = self._tenant_path(tenant_id) / category
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / filename
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(text)
        return str(file_path)

    async def read_text(self, path: str) -> str:
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            return await f.read()


storage = LocalStorageBackend()
