import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.analysis import Analysis, Prediction, AnalysisStatus
from app.repositories.base import BaseRepository


class AnalysisRepository(BaseRepository[Analysis]):
    def __init__(self, db: AsyncSession):
        super().__init__(Analysis, db)

    async def get_by_id_detailed(self, analysis_id: uuid.UUID) -> Optional[Analysis]:
        query = (
            select(Analysis)
            .where(Analysis.id == analysis_id)
            .options(
                selectinload(Analysis.image),
                selectinload(Analysis.prediction),
                selectinload(Analysis.review),
            )
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_user_analyses(
        self, user_id: uuid.UUID, limit: int = 20, offset: int = 0
    ) -> Tuple[List[Analysis], int]:
        count_query = select(func.count(Analysis.id)).where(Analysis.user_id == user_id)
        count_res = await self.db.execute(count_query)
        total = count_res.scalar() or 0

        query = (
            select(Analysis)
            .where(Analysis.user_id == user_id)
            .options(
                selectinload(Analysis.image),
                selectinload(Analysis.prediction),
                selectinload(Analysis.review),
            )
            .order_by(desc(Analysis.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_all_analyses(
        self, limit: int = 20, offset: int = 0
    ) -> Tuple[List[Analysis], int]:
        count_query = select(func.count(Analysis.id))
        count_res = await self.db.execute(count_query)
        total = count_res.scalar() or 0

        query = (
            select(Analysis)
            .options(
                selectinload(Analysis.image),
                selectinload(Analysis.prediction),
                selectinload(Analysis.review),
            )
            .order_by(desc(Analysis.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def create_prediction(self, prediction: Prediction) -> Prediction:
        self.db.add(prediction)
        await self.db.commit()
        await self.db.refresh(prediction)
        return prediction

    async def get_analysis_statistics(self) -> Dict[str, Any]:
        """Aggregate analysis statistics for admin dashboard."""
        total_q = await self.db.execute(select(func.count(Analysis.id)))
        total = total_q.scalar() or 0

        completed_q = await self.db.execute(
            select(func.count(Analysis.id)).where(Analysis.status == AnalysisStatus.COMPLETED)
        )
        completed = completed_q.scalar() or 0

        failed_q = await self.db.execute(
            select(func.count(Analysis.id)).where(Analysis.status == AnalysisStatus.FAILED)
        )
        failed = failed_q.scalar() or 0

        pending_q = await self.db.execute(
            select(func.count(Analysis.id)).where(
                Analysis.status.in_([AnalysisStatus.PENDING, AnalysisStatus.PROCESSING])
            )
        )
        pending = pending_q.scalar() or 0

        avg_time_q = await self.db.execute(
            select(func.avg(Analysis.processing_time_ms)).where(
                Analysis.status == AnalysisStatus.COMPLETED
            )
        )
        avg_time = avg_time_q.scalar() or 0.0

        # Class breakdown
        class_dist_q = await self.db.execute(
            select(Prediction.predicted_class, func.count(Prediction.id)).group_by(
                Prediction.predicted_class
            )
        )
        class_counts = class_dist_q.all()

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "avg_time_ms": round(float(avg_time), 2),
            "class_counts": {row[0]: row[1] for row in class_counts},
        }
