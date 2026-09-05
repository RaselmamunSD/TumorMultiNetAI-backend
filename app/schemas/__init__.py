from app.schemas.common import APIResponse, ErrorDetail, ErrorResponse, PaginationMeta, PaginatedResponse
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    TokenResponse,
    RefreshTokenRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
    EmailVerificationRequest,
)
from app.schemas.user import UserResponse, UserUpdate, PatientProfileResponse, DoctorProfileResponse, RoleResponse
from app.schemas.analysis import (
    MedicalImageResponse,
    PredictionDetail,
    PredictionResponse,
    ExplainabilityResponse,
    AnalysisStatusResponse,
    AnalysisListItem,
    AnalysisDetailResponse,
)
from app.schemas.review import ReviewCreate, ReviewUpdate, ReviewResponse
from app.schemas.ml_model import MLModelCreate, MLModelUpdate, MLModelResponse
from app.schemas.admin import AdminDashboardStats, SystemHealthStats, AuditLogResponse

__all__ = [
    "APIResponse",
    "ErrorDetail",
    "ErrorResponse",
    "PaginationMeta",
    "PaginatedResponse",
    "UserRegister",
    "UserLogin",
    "TokenResponse",
    "RefreshTokenRequest",
    "PasswordResetRequest",
    "PasswordResetConfirm",
    "EmailVerificationRequest",
    "UserResponse",
    "UserUpdate",
    "PatientProfileResponse",
    "DoctorProfileResponse",
    "RoleResponse",
    "MedicalImageResponse",
    "PredictionDetail",
    "PredictionResponse",
    "ExplainabilityResponse",
    "AnalysisStatusResponse",
    "AnalysisListItem",
    "AnalysisDetailResponse",
    "ReviewCreate",
    "ReviewUpdate",
    "ReviewResponse",
    "MLModelCreate",
    "MLModelUpdate",
    "MLModelResponse",
    "AdminDashboardStats",
    "SystemHealthStats",
    "AuditLogResponse",
]
