import os
import asyncio
from pathlib import Path
from typing import Optional
from app.core.config import settings
from app.storage.base import StorageBackend


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage implementation with async executor."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or settings.LOCAL_STORAGE_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _sync_save(self, file_path: Path, data: bytes) -> None:
        with open(file_path, "wb") as f:
            f.write(data)

    def _sync_read(self, file_path: Path) -> bytes:
        with open(file_path, "rb") as f:
            return f.read()

    async def save_file(self, file_data: bytes, file_name: str, subfolder: str = "") -> str:
        target_dir = self.base_dir / subfolder if subfolder else self.base_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / file_name

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._sync_save, file_path, file_data)

        if subfolder:
            return f"{subfolder}/{file_name}".replace("\\", "/")
        return file_name

    async def read_file(self, storage_path: str) -> bytes:
        file_path = (self.base_dir / storage_path).resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"File not found at {storage_path}")

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_read, file_path)

    async def delete_file(self, storage_path: str) -> bool:
        file_path = (self.base_dir / storage_path).resolve()
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    async def file_exists(self, storage_path: str) -> bool:
        file_path = (self.base_dir / storage_path).resolve()
        return file_path.exists()
