from abc import ABC, abstractmethod
from typing import BinaryIO, Optional


class StorageBackend(ABC):
    """Abstract interface for file storage implementations."""

    @abstractmethod
    async def save_file(self, file_data: bytes, file_name: str, subfolder: str = "") -> str:
        """Save bytes data and return relative/accessible storage path."""
        pass

    @abstractmethod
    async def read_file(self, storage_path: str) -> bytes:
        """Read bytes from storage path."""
        pass

    @abstractmethod
    async def delete_file(self, storage_path: str) -> bool:
        """Delete file at storage path."""
        pass

    @abstractmethod
    async def file_exists(self, storage_path: str) -> bool:
        """Check if file exists in storage."""
        pass
