import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import RoleChecker, get_current_user
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.review import ReviewCreate, ReviewResponse
from app.services.review_service import ReviewService
from app.services.audit_service import AuditService

router = APIRouter(
    prefix="/doctors",
    tags=["Doctor & Radiologist Reviews"],
    dependencies=[Depends(RoleChecker(allowed_roles=["Doctor", "Radiologist", "Admin"]))],
)


@router.post(
    "/analysis/{analysis_id}/review",
    response_model=APIResponse[ReviewResponse],
    status_code=status.HTTP_200_OK,
    summary="Submit or Update Clinical Review",
    description="Allows licensed doctors and radiologists to submit professional clinical findings and recommendations.",
)
async def submit_clinical_review(
    analysis_id: uuid.UUID,
    payload: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    review_service = ReviewService(db)
    review = await review_service.add_or_update_review(
        analysis_id=analysis_id, reviewer=current_user, payload=payload
    )

    audit_service = AuditService(db)
    await audit_service.log_action(
        action="SUBMIT_CLINICAL_REVIEW",
        resource_type="AnalysisReview",
        resource_id=str(review.id),
        user_id=current_user.id,
        details={"status": review.status.value, "analysis_id": str(analysis_id)},
    )

    specialty = current_user.doctor_profile.specialty if current_user.doctor_profile else "Doctor"

    return APIResponse(
        success=True,
        message="Clinical review recorded successfully.",
        data=ReviewResponse(
            id=review.id,
            analysis_id=review.analysis_id,
            reviewer_id=review.reviewer_id,
            reviewer_name=current_user.full_name,
            reviewer_specialty=specialty,
            status=review.status,
            clinical_notes=review.clinical_notes,
            recommendations=review.recommendations,
            created_at=review.created_at,
            updated_at=review.updated_at,
        ),
    )


@router.get(
    "/analysis/{analysis_id}/review",
    response_model=APIResponse[ReviewResponse],
    summary="Get Clinical Review for Analysis",
)
async def get_clinical_review(
    analysis_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    review_service = ReviewService(db)
    review = await review_service.get_review_by_analysis(analysis_id)

    if not review:
        return APIResponse(success=True, message="No review recorded yet.", data=None)

    reviewer_name = review.reviewer.full_name if review.reviewer else "Unknown Reviewer"
    reviewer_specialty = (
        review.reviewer.doctor_profile.specialty
        if review.reviewer and review.reviewer.doctor_profile
        else "Doctor"
    )

    return APIResponse(
        success=True,
        data=ReviewResponse(
            id=review.id,
            analysis_id=review.analysis_id,
            reviewer_id=review.reviewer_id,
            reviewer_name=reviewer_name,
            reviewer_specialty=reviewer_specialty,
            status=review.status,
            clinical_notes=review.clinical_notes,
            recommendations=review.recommendations,
            created_at=review.created_at,
            updated_at=review.updated_at,
        ),
    )
