import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.analysis import AnalysisReview
from app.repositories.base import BaseRepository


class ReviewRepository(BaseRepository[AnalysisReview]):
    def __init__(self, db: AsyncSession):
        super().__init__(AnalysisReview, db)

    async def get_by_analysis_id(self, analysis_id: uuid.UUID) -> Optional[AnalysisReview]:
        query = (
            select(AnalysisReview)
            .where(AnalysisReview.analysis_id == analysis_id)
            .options(selectinload(AnalysisReview.reviewer))
        )
        result = await self.db.execute(query)
        return result.scalars().first()
