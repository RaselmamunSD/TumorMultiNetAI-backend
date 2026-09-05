import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from app.models.analysis import ReviewStatus


class ReviewCreate(BaseModel):
    status: ReviewStatus = Field(..., description="confirmed_abnormal, confirmed_normal, inconclusive, disputed")
    clinical_notes: str = Field(..., min_length=10, description="Detailed medical evaluation notes from the doctor/radiologist.")
    recommendations: Optional[str] = Field(None, description="Recommended next steps (e.g., contrast MRI, biopsy, follow-up in 3 months).")


class ReviewUpdate(BaseModel):
    status: Optional[ReviewStatus] = None
    clinical_notes: Optional[str] = Field(None, min_length=10)
    recommendations: Optional[str] = None


class ReviewResponse(BaseModel):
    id: uuid.UUID
    analysis_id: uuid.UUID
    reviewer_id: uuid.UUID
    reviewer_name: Optional[str] = None
    reviewer_specialty: Optional[str] = None
    status: ReviewStatus
    clinical_notes: str
    recommendations: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
