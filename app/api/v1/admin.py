from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import RoleChecker
from app.models.user import User
from app.repositories.audit_repo import AuditLogRepository
from app.repositories.ml_model_repo import MLModelRepository
from app.schemas.admin import AdminDashboardStats, AuditLogResponse
from app.schemas.common import APIResponse, PaginatedResponse, PaginationMeta
from app.schemas.ml_model import MLModelCreate, MLModelResponse
from app.services.admin_service import AdminService

router = APIRouter(
    prefix="/admin",
    tags=["Admin Dashboard"],
    dependencies=[Depends(RoleChecker(allowed_roles=["Admin"]))],
)


@router.get(
    "/stats",
    response_model=APIResponse[AdminDashboardStats],
    summary="Admin Dashboard Statistics",
    description="Returns aggregated metrics for users, analyses, model usage, and prediction distributions.",
)
async def get_admin_stats(db: AsyncSession = Depends(get_db)):
    admin_service = AdminService(db)
    stats = await admin_service.get_dashboard_metrics()
    return APIResponse(success=True, data=stats)


@router.get(
    "/audit-logs",
    response_model=APIResponse[PaginatedResponse[AuditLogResponse]],
    summary="View System Audit Logs",
    description="HIPAA compliant audit trail inspection for patient data and analysis events.",
)
async def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    repo = AuditLogRepository(db)
    offset = (page - 1) * page_size
    logs, total = await repo.get_logs_paginated(limit=page_size, offset=offset)

    items = [AuditLogResponse.model_validate(log) for log in logs]
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 1

    return APIResponse(
        success=True,
        data=PaginatedResponse(
            items=items,
            pagination=PaginationMeta(
                page=page,
                page_size=page_size,
                total_items=total,
                total_pages=total_pages,
                has_next=page < total_pages,
                has_previous=page > 1,
            ),
        ),
    )


@router.get(
    "/models",
    response_model=APIResponse[List[MLModelResponse]],
    summary="List Registered AI Models",
)
async def list_models(db: AsyncSession = Depends(get_db)):
    repo = MLModelRepository(db)
    models = await repo.get_all()
    return APIResponse(
        success=True,
        data=[MLModelResponse.model_validate(m) for m in models],
    )


@router.post(
    "/models",
    response_model=APIResponse[MLModelResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register New AI Model Version",
)
async def register_model(
    payload: MLModelCreate,
    db: AsyncSession = Depends(get_db),
):
    admin_service = AdminService(db)
    model = await admin_service.register_or_update_model(
        name=payload.name,
        version=payload.version,
        architecture=payload.architecture,
        weights_path=payload.weights_path,
        description=payload.description,
        accuracy=payload.accuracy,
        f1_score=payload.f1_score,
        auc_roc=payload.auc_roc,
        supported_classes=payload.supported_classes,
        is_active=payload.is_active,
    )
    return APIResponse(
        success=True,
        message="ML Model version registered successfully.",
        data=MLModelResponse.model_validate(model),
    )
