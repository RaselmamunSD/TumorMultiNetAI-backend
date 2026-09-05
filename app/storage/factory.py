from functools import lru_cache
from app.core.config import settings
from app.storage.base import StorageBackend
from app.storage.local import LocalStorageBackend
from app.storage.s3 import S3StorageBackend


@lru_cache()
def get_storage_backend() -> StorageBackend:
    """Factory function resolving configured storage backend."""
    backend_type = settings.STORAGE_BACKEND.lower()
    if backend_type in ["s3", "minio", "r2"]:
        return S3StorageBackend()
    return LocalStorageBackend()
