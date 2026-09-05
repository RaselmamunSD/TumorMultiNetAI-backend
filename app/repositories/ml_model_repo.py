from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ml_model import MLModel
from app.repositories.base import BaseRepository


class MLModelRepository(BaseRepository[MLModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(MLModel, db)

    async def get_by_name(self, name: str) -> Optional[MLModel]:
        query = select(MLModel).where(MLModel.name == name)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_active_model(self) -> Optional[MLModel]:
        query = select(MLModel).where(MLModel.is_active == True).order_by(MLModel.created_at.desc())
        result = await self.db.execute(query)
        return result.scalars().first()
