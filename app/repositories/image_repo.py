import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.analysis import MedicalImage
from app.repositories.base import BaseRepository


class MedicalImageRepository(BaseRepository[MedicalImage]):
    def __init__(self, db: AsyncSession):
        super().__init__(MedicalImage, db)

    async def get_by_hash(self, sha256_hash: str) -> Optional[MedicalImage]:
        query = select(MedicalImage).where(MedicalImage.file_hash_sha256 == sha256_hash)
        result = await self.db.execute(query)
        return result.scalars().first()
