import uuid
from typing import List, Optional
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, rate_limit_dependency
from app.models.analysis import AnalysisStatus
from app.models.user import User
from app.schemas.analysis import (
    AnalysisDetailResponse,
    AnalysisListItem,
    AnalysisStatusResponse,
    ExplainabilityResponse,
    PredictionDetail,
    PredictionResponse,
)
from app.schemas.common import APIResponse, PaginatedResponse, PaginationMeta
from app.services.analysis_service import AnalysisService
from app.services.audit_service import AuditService
from app.storage.factory import get_storage_backend
from app.tasks.worker_tasks import process_mri_analysis_task

router = APIRouter(prefix="/analysis", tags=["MRI Analysis"], dependencies=[Depends(rate_limit_dependency)])


@router.post(
    "/upload",
    response_model=APIResponse[PredictionResponse],
    status_code=status.HTTP_200_OK,
    summary="Upload and Analyze Brain MRI Image",
    description=(
        "Upload a brain MRI scan (.dcm, .png, .jpg, .jpeg) for AI screening analysis. "
        "Supports both synchronous instant inference (default) and asynchronous background processing."
    ),
)
async def upload_mri_image(
    request: Request,
    file: UploadFile = File(..., description="Brain MRI scan file in DICOM, PNG, or JPEG format."),
    async_mode: bool = Query(False, description="Set to true for asynchronous Celery worker processing."),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    file_bytes = await file.read()
    filename = file.filename or "upload.png"

    analysis_service = AnalysisService(db)
    medical_image, analysis = await analysis_service.upload_and_create_analysis(
        file_bytes=file_bytes,
        original_filename=filename,
        user=current_user,
    )

    # HIPAA audit trail
    audit_service = AuditService(db)
    await audit_service.log_action(
        action="UPLOAD_MRI_IMAGE",
        resource_type="MedicalImage",
        resource_id=str(medical_image.id),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        details={"file_name": medical_image.file_name, "modality": medical_image.image_modality},
    )

    if async_mode:
        # Dispatch background Celery task
        process_mri_analysis_task.delay(str(analysis.id))
        return APIResponse(
            success=True,
            message="MRI scan uploaded successfully and queued for asynchronous processing.",
            data=PredictionResponse(
                analysis_id=analysis.id,
                status=AnalysisStatus.PENDING,
                disclaimer=settings.MEDICAL_DISCLAIMER,
            ),
        )

    # Synchronous processing
    prediction = await analysis_service.process_sync_prediction(
        analysis_id=analysis.id,
        file_bytes=file_bytes,
        filename=filename,
    )

    prediction_detail = PredictionDetail(
        predicted_class=prediction.predicted_class,
        screening_label=prediction.screening_label,
        confidence=prediction.confidence,
        is_abnormal=prediction.is_abnormal,
    )

    return APIResponse(
        success=True,
        message="AI screening analysis completed.",
        data=PredictionResponse(
            analysis_id=analysis.id,
            status=AnalysisStatus.COMPLETED,
            prediction=prediction_detail,
            probabilities=prediction.probabilities,
            model_name=prediction.model_name,
            model_version=prediction.model_version,
            processing_time_ms=analysis.processing_time_ms,
            disclaimer=prediction.disclaimer,
        ),
    )


@router.get(
    "/{analysis_id}/status",
    response_model=APIResponse[AnalysisStatusResponse],
    summary="Check Async Analysis Status",
)
async def get_analysis_status(
    analysis_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    analysis_service = AnalysisService(db)
    analysis = await analysis_service.get_analysis_for_user(analysis_id, current_user)

    return APIResponse(
        success=True,
        data=AnalysisStatusResponse(
            analysis_id=analysis.id,
            status=analysis.status,
            progress=analysis.progress_percentage,
            error_message=analysis.error_message,
        ),
    )


@router.get(
    "/history",
    response_model=APIResponse[PaginatedResponse[AnalysisListItem]],
    summary="Get Analysis History",
)
async def get_analysis_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    analysis_service = AnalysisService(db)
    offset = (page - 1) * page_size
    analyses, total = await analysis_service.list_user_history(
        user=current_user, limit=page_size, offset=offset
    )

    items = []
    for a in analyses:
        pred_resp = None
        if a.prediction:
            pred_resp = PredictionResponse(
                analysis_id=a.id,
                status=a.status,
                prediction=PredictionDetail(
                    predicted_class=a.prediction.predicted_class,
                    screening_label=a.prediction.screening_label,
                    confidence=a.prediction.confidence,
                    is_abnormal=a.prediction.is_abnormal,
                ),
                probabilities=a.prediction.probabilities,
                model_name=a.prediction.model_name,
                model_version=a.prediction.model_version,
                processing_time_ms=a.processing_time_ms,
                disclaimer=a.prediction.disclaimer,
            )

        items.append(
            AnalysisListItem(
                id=a.id,
                image=a.image,
                status=a.status,
                progress_percentage=a.progress_percentage,
                prediction=pred_resp,
                created_at=a.created_at,
            )
        )

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
    "/{analysis_id}",
    response_model=APIResponse[AnalysisDetailResponse],
    summary="Get Analysis Detail",
)
async def get_analysis_detail(
    analysis_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    analysis_service = AnalysisService(db)
    analysis = await analysis_service.get_analysis_for_user(analysis_id, current_user)

    # HIPAA audit trail
    audit_service = AuditService(db)
    await audit_service.log_action(
        action="VIEW_ANALYSIS_DETAIL",
        resource_type="Analysis",
        resource_id=str(analysis.id),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    pred_resp = None
    if analysis.prediction:
        pred_resp = PredictionResponse(
            analysis_id=analysis.id,
            status=analysis.status,
            prediction=PredictionDetail(
                predicted_class=analysis.prediction.predicted_class,
                screening_label=analysis.prediction.screening_label,
                confidence=analysis.prediction.confidence,
                is_abnormal=analysis.prediction.is_abnormal,
            ),
            probabilities=analysis.prediction.probabilities,
            model_name=analysis.prediction.model_name,
            model_version=analysis.prediction.model_version,
            processing_time_ms=analysis.processing_time_ms,
            disclaimer=analysis.prediction.disclaimer,
        )

    return APIResponse(
        success=True,
        data=AnalysisDetailResponse(
            id=analysis.id,
            user_id=analysis.user_id,
            image=analysis.image,
            status=analysis.status,
            progress_percentage=analysis.progress_percentage,
            prediction=pred_resp,
            error_message=analysis.error_message,
            processing_time_ms=analysis.processing_time_ms,
            created_at=analysis.created_at,
            updated_at=analysis.updated_at,
        ),
    )


@router.post(
    "/{analysis_id}/explain",
    response_model=APIResponse[ExplainabilityResponse],
    summary="Generate Explainable AI (Grad-CAM) Visual Heatmap",
    description="Generates visual interpretability heatmaps and blended overlays highlighting regions of interest.",
)
async def explain_analysis(
    analysis_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    analysis_service = AnalysisService(db)
    result = await analysis_service.generate_explainability(analysis_id, current_user)

    audit_service = AuditService(db)
    await audit_service.log_action(
        action="GENERATE_XAI_GRADCAM",
        resource_type="Analysis",
        resource_id=str(analysis_id),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return APIResponse(
        success=True,
        message="Grad-CAM visualization generated successfully.",
        data=ExplainabilityResponse(**result),
    )


@router.delete(
    "/{analysis_id}",
    response_model=APIResponse[dict],
    summary="Delete Analysis and Images",
)
async def delete_analysis(
    analysis_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    analysis_service = AnalysisService(db)
    await analysis_service.delete_analysis(analysis_id, current_user)

    audit_service = AuditService(db)
    await audit_service.log_action(
        action="DELETE_ANALYSIS",
        resource_type="Analysis",
        resource_id=str(analysis_id),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return APIResponse(success=True, message="Analysis record and associated media deleted.")


@router.get(
    "/file/{file_path:path}",
    summary="Secure Medical Image Retrieval",
    description="Streams stored medical scans or Grad-CAM overlays securely for authenticated users.",
)
async def get_storage_file(
    file_path: str,
    current_user: User = Depends(get_current_user),
):
    storage = get_storage_backend()
    if not await storage.file_exists(file_path):
        raise HTTPException(status_code=404, detail="Requested file not found.")

    file_bytes = await storage.read_file(file_path)
    content_type = "image/png"
    if file_path.endswith((".jpg", ".jpeg")):
        content_type = "image/jpeg"
    elif file_path.endswith(".dcm"):
        content_type = "application/dicom"

    return Response(content=file_bytes, media_type=content_type)
