import asyncio
from typing import Optional
import boto3
from botocore.exceptions import ClientError
from app.core.config import settings
from app.storage.base import StorageBackend


class S3StorageBackend(StorageBackend):
    """Amazon S3 / MinIO / Cloudflare R2 storage backend."""

    def __init__(self):
        self.bucket_name = settings.AWS_S3_BUCKET
        session = boto3.session.Session()
        self.s3_client = session.client(
            service_name="s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
            region_name=settings.AWS_REGION,
            endpoint_url=settings.AWS_S3_ENDPOINT_URL or None,
        )

    def _sync_upload(self, key: str, data: bytes) -> None:
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=data,
            ServerSideEncryption="AES256",
        )

    def _sync_download(self, key: str) -> bytes:
        response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
        return response["Body"].read()

    def _sync_delete(self, key: str) -> bool:
        self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
        return True

    def _sync_exists(self, key: str) -> bool:
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError:
            return False

    async def save_file(self, file_data: bytes, file_name: str, subfolder: str = "") -> str:
        key = f"{subfolder}/{file_name}".lstrip("/") if subfolder else file_name
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._sync_upload, key, file_data)
        return key

    async def read_file(self, storage_path: str) -> bytes:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_download, storage_path)

    async def delete_file(self, storage_path: str) -> bool:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_delete, storage_path)

    async def file_exists(self, storage_path: str) -> bool:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_exists, storage_path)
