import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ClassPredictionStat(BaseModel):
    class_name: str
    count: int
    percentage: float


class AdminDashboardStats(BaseModel):
    total_users: int
    total_patients: int
    total_doctors: int
    total_analyses: int
    successful_analyses: int
    failed_analyses: int
    pending_analyses: int
    average_processing_time_ms: float
    total_reviews_completed: int
    class_distribution: List[ClassPredictionStat]
    active_ml_model: Optional[str] = None
    active_ml_version: Optional[str] = None


class SystemHealthStats(BaseModel):
    status: str
    database: str
    redis: str
    ml_model: str
    storage: str
    active_workers: int
    timestamp: datetime


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True
