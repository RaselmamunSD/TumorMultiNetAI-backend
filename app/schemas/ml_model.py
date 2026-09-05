import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MLModelCreate(BaseModel):
    name: str = Field(..., max_length=100)
    version: str = Field(..., max_length=50)
    framework: str = Field("PyTorch", max_length=50)
    architecture: str = Field(..., max_length=100)
    weights_path: str = Field(..., max_length=500)
    description: Optional[str] = None
    accuracy: Optional[float] = None
    f1_score: Optional[float] = None
    auc_roc: Optional[float] = None
    supported_classes: List[str] = ["no_tumor", "glioma", "meningioma", "pituitary"]
    is_active: bool = True


class MLModelUpdate(BaseModel):
    is_active: Optional[bool] = None
    description: Optional[str] = None
    accuracy: Optional[float] = None
    f1_score: Optional[float] = None
    auc_roc: Optional[float] = None


class MLModelResponse(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    framework: str
    architecture: str
    description: Optional[str] = None
    accuracy: Optional[float] = None
    f1_score: Optional[float] = None
    auc_roc: Optional[float] = None
    supported_classes: Any
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
