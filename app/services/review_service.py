import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import NotFoundException, ForbiddenException
from app.models.analysis import AnalysisReview, ReviewStatus
from app.models.user import User
from app.repositories.analysis_repo import AnalysisRepository
from app.repositories.review_repo import ReviewRepository
from app.schemas.review import ReviewCreate, ReviewUpdate


class ReviewService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.review_repo = ReviewRepository(db)
        self.analysis_repo = AnalysisRepository(db)

    async def add_or_update_review(
        self, analysis_id: uuid.UUID, reviewer: User, payload: ReviewCreate
    ) -> AnalysisReview:
        # Check doctor/radiologist role
        is_medical_expert = any(r.name.lower() in ["doctor", "radiologist", "admin"] for r in reviewer.roles)
        if not is_medical_expert:
            raise ForbiddenException("Only licensed medical doctors or radiologists can submit clinical reviews.")

        analysis = await self.analysis_repo.get_by_id_detailed(analysis_id)
        if not analysis:
            raise NotFoundException("Analysis record not found.")

        existing_review = await self.review_repo.get_by_analysis_id(analysis_id)
        if existing_review:
            existing_review.status = payload.status
            existing_review.clinical_notes = payload.clinical_notes
            existing_review.recommendations = payload.recommendations
            existing_review.reviewer_id = reviewer.id
            return await self.review_repo.update(existing_review)

        review = AnalysisReview(
            analysis_id=analysis.id,
            reviewer_id=reviewer.id,
            status=payload.status,
            clinical_notes=payload.clinical_notes,
            recommendations=payload.recommendations,
        )
        return await self.review_repo.create(review)

    async def get_review_by_analysis(self, analysis_id: uuid.UUID) -> Optional[AnalysisReview]:
        return await self.review_repo.get_by_analysis_id(analysis_id)
