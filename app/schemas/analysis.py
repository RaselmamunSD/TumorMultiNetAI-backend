import uuid
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from app.models.analysis import AnalysisStatus, ReviewStatus


class MedicalImageResponse(BaseModel):
    id: uuid.UUID
    file_name: str
    mime_type: str
    file_size_bytes: int
    width: Optional[int] = None
    height: Optional[int] = None
    image_modality: str
    created_at: datetime

    class Config:
        from_attributes = True


class PredictionDetail(BaseModel):
    predicted_class: str
    screening_label: str
    confidence: float
    is_abnormal: bool


class PredictionResponse(BaseModel):
    analysis_id: uuid.UUID
    status: AnalysisStatus
    prediction: Optional[PredictionDetail] = None
    probabilities: Optional[Dict[str, float]] = None
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    processing_time_ms: Optional[float] = None
    disclaimer: str

    class Config:
        from_attributes = True


class ExplainabilityResponse(BaseModel):
    analysis_id: uuid.UUID
    gradcam_url: Optional[str] = None
    overlay_url: Optional[str] = None
    target_class: str
    explanation_note: str = (
        "AI Grad-CAM attention heatmap highlights the image regions that contributed most to the model prediction. "
        "This visual aid is for decision-support and interpretability only and must not be used as a definitive surgical or tumor margin."
    )


class AnalysisStatusResponse(BaseModel):
    analysis_id: uuid.UUID
    status: AnalysisStatus
    progress: int
    error_message: Optional[str] = None


class AnalysisListItem(BaseModel):
    id: uuid.UUID
    image: MedicalImageResponse
    status: AnalysisStatus
    progress_percentage: int
    prediction: Optional[PredictionResponse] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AnalysisDetailResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    image: MedicalImageResponse
    status: AnalysisStatus
    progress_percentage: int
    prediction: Optional[PredictionResponse] = None
    error_message: Optional[str] = None
    processing_time_ms: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
