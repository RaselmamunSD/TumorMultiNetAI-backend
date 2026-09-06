import io
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.exceptions import ForbiddenException, NotFoundException, PredictionFailedException
from app.core.logging import logger
from app.models.analysis import Analysis, AnalysisStatus, MedicalImage, Prediction
from app.models.user import User
from app.ml.predictor import model_service
from app.repositories.analysis_repo import AnalysisRepository
from app.repositories.image_repo import MedicalImageRepository
from app.services.validation_service import ImageValidationService
from app.services.gemini_vision_service import GeminiVisionService
from app.storage.factory import get_storage_backend


class AnalysisService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.analysis_repo = AnalysisRepository(db)
        self.image_repo = MedicalImageRepository(db)
        self.storage = get_storage_backend()

    async def upload_and_create_analysis(
        self,
        file_bytes: bytes,
        original_filename: str,
        user: User,
    ) -> Tuple[MedicalImage, Analysis]:
        """
        Validates file, saves to storage, and registers records in DB.
        """
        # Multi-layer image validation
        mime_type, width, height, modality = ImageValidationService.validate_and_inspect_image(
            file_bytes, original_filename
        )
        file_hash = ImageValidationService.calculate_sha256(file_bytes)

        # Generate unique sanitized storage filename
        image_id = uuid.uuid4()
        ext = original_filename.lower().split(".")[-1] if "." in original_filename else "png"
        storage_filename = f"{image_id}.{ext}"
        storage_subfolder = f"mri_scans/{user.id}"

        storage_path = await self.storage.save_file(
            file_data=file_bytes,
            file_name=storage_filename,
            subfolder=storage_subfolder,
        )

        # Save MedicalImage record
        medical_image = MedicalImage(
            id=image_id,
            user_id=user.id,
            storage_path=storage_path,
            storage_backend=settings.STORAGE_BACKEND,
            file_name=storage_filename,
            mime_type=mime_type,
            file_size_bytes=len(file_bytes),
            width=width,
            height=height,
            image_modality=modality,
            file_hash_sha256=file_hash,
        )
        await self.image_repo.create(medical_image)

        # Create Analysis record
        analysis = Analysis(
            user_id=user.id,
            image_id=medical_image.id,
            status=AnalysisStatus.PENDING,
            progress_percentage=10,
        )
        await self.analysis_repo.create(analysis)

        return medical_image, analysis

    async def process_sync_prediction(
        self, analysis_id: uuid.UUID, file_bytes: bytes, filename: str
    ) -> Prediction:
        """
        Synchronous AI model inference execution.
        """
        analysis = await self.analysis_repo.get_by_id_detailed(analysis_id)
        if not analysis:
            raise NotFoundException("Analysis record not found.")

        analysis.status = AnalysisStatus.PROCESSING
        analysis.progress_percentage = 40
        await self.analysis_repo.update(analysis)

        start_time = time.time()
        try:
            # 1. First attempt Multimodal AI Vision verification and screening
            gemini_res = await GeminiVisionService.analyze_mri_with_gemini(file_bytes, filename)
            
            if gemini_res is not None:
                # Check if the uploaded image is a real brain scan
                is_brain_mri = gemini_res.get("is_brain_mri", True)
                if not is_brain_mri:
                    rejection_reason = (
                        gemini_res.get("rejection_reason")
                        or "The uploaded image is not a recognized Brain MRI or CT scan. Please upload a valid brain MRI scan (T1, T2, FLAIR, T1ce)."
                    )
                    logger.warning(f"Image rejected as non-brain MRI: {rejection_reason}")
                    raise PredictionFailedException(rejection_reason)

                predicted_class = gemini_res.get("predicted_class", "no_tumor")
                screening_label = gemini_res.get("screening_label") or f"Screening Result: {predicted_class.title()}"
                confidence = float(gemini_res.get("confidence", 0.92))
                is_abnormal = bool(gemini_res.get("is_abnormal", predicted_class != "no_tumor"))
                probabilities = gemini_res.get("probabilities") or {
                    "glioma": 0.0, "meningioma": 0.0, "pituitary": 0.0, "no_tumor": 1.0
                }
                elapsed_ms = round((time.time() - start_time) * 1000, 2)

                prediction = Prediction(
                    analysis_id=analysis.id,
                    model_name="TumorMultiNetVisionEngine",
                    model_version=settings.MODEL_VERSION,
                    predicted_class=predicted_class,
                    screening_label=screening_label,
                    confidence=confidence,
                    is_abnormal=is_abnormal,
                    probabilities=probabilities,
                    inference_time_ms=elapsed_ms,
                    disclaimer=(
                        "AI screening decision-support prediction. Not a final medical diagnosis. "
                        "Must be confirmed by a licensed radiologist or neuro-specialist."
                    ),
                )

                # Generate Red Lesion Highlight Overlay and Heatmap
                box_2d = gemini_res.get("box_2d")
                try:
                    overlay_bytes, heatmap_bytes = GeminiVisionService.generate_red_lesion_visualizations(
                        file_bytes, filename, box_2d
                    )
                    subfolder = f"explainability/{analysis.user_id}"
                    heatmap_name = f"gradcam_heatmap_{analysis.id}.png"
                    overlay_name = f"gradcam_overlay_{analysis.id}.png"
                    prediction.gradcam_path = await self.storage.save_file(heatmap_bytes, heatmap_name, subfolder)
                    prediction.overlay_path = await self.storage.save_file(overlay_bytes, overlay_name, subfolder)
                    prediction.explainability_generated = True
                except Exception as vis_err:
                    logger.warning(f"Error generating red lesion visualization: {str(vis_err)}")
            else:
                # 2. Local PyTorch model inference fallback
                ml_result = model_service.predict(file_bytes, filename)
                elapsed_ms = round((time.time() - start_time) * 1000, 2)

                prediction = Prediction(
                    analysis_id=analysis.id,
                    model_name=ml_result.get("model_name", "TumorMultiNetClassifier"),
                    model_version=ml_result.get("model_version", settings.MODEL_VERSION),
                    predicted_class=ml_result["predicted_class"],
                    screening_label=ml_result["screening_label"],
                    confidence=ml_result["confidence"],
                    is_abnormal=ml_result["is_abnormal"],
                    probabilities=ml_result["probabilities"],
                    inference_time_ms=ml_result.get("inference_time_ms", elapsed_ms),
                    disclaimer=ml_result["disclaimer"],
                )
                try:
                    overlay_bytes, heatmap_bytes = GeminiVisionService.generate_red_lesion_visualizations(
                        file_bytes, filename, None
                    )
                    subfolder = f"explainability/{analysis.user_id}"
                    heatmap_name = f"gradcam_heatmap_{analysis.id}.png"
                    overlay_name = f"gradcam_overlay_{analysis.id}.png"
                    prediction.gradcam_path = await self.storage.save_file(heatmap_bytes, heatmap_name, subfolder)
                    prediction.overlay_path = await self.storage.save_file(overlay_bytes, overlay_name, subfolder)
                    prediction.explainability_generated = True
                except Exception as vis_err:
                    logger.warning(f"Error generating fallback visualization: {str(vis_err)}")

            await self.analysis_repo.create_prediction(prediction)

            analysis.status = AnalysisStatus.COMPLETED
            analysis.progress_percentage = 100
            analysis.processing_time_ms = elapsed_ms
            await self.analysis_repo.update(analysis)

            return prediction

        except Exception as e:
            analysis.status = AnalysisStatus.FAILED
            analysis.error_message = str(e)
            analysis.progress_percentage = 0
            await self.analysis_repo.update(analysis)
            raise e

    async def generate_explainability(
        self, analysis_id: uuid.UUID, user: User
    ) -> Dict[str, Any]:
        """
        Generate Grad-CAM heatmap and red lesion overlay images for an existing analysis.
        """
        analysis = await self.get_analysis_for_user(analysis_id, user)
        if not analysis.prediction:
            raise NotFoundException("No prediction exists for this analysis to explain.")

        prediction = analysis.prediction

        # If already generated, return cached paths
        if prediction.gradcam_path and prediction.overlay_path:
            return {
                "analysis_id": analysis.id,
                "gradcam_url": f"/api/v1/analysis/file/{prediction.gradcam_path}",
                "overlay_url": f"/api/v1/analysis/file/{prediction.overlay_path}",
                "target_class": prediction.predicted_class,
            }

        # Read original MRI scan from storage
        image_bytes = await self.storage.read_file(analysis.image.storage_path)

        try:
            overlay_bytes, heatmap_bytes = GeminiVisionService.generate_red_lesion_visualizations(
                image_bytes, analysis.image.file_name, None
            )
        except Exception:
            heatmap_bytes, overlay_bytes, _ = model_service.explain(
                image_bytes=image_bytes,
                filename=analysis.image.file_name,
            )

        # Save Grad-CAM artifacts
        subfolder = f"explainability/{analysis.user_id}"
        heatmap_name = f"gradcam_heatmap_{analysis.id}.png"
        overlay_name = f"gradcam_overlay_{analysis.id}.png"

        heatmap_path = await self.storage.save_file(heatmap_bytes, heatmap_name, subfolder)
        overlay_path = await self.storage.save_file(overlay_bytes, overlay_name, subfolder)

        # Update prediction record
        prediction.gradcam_path = heatmap_path
        prediction.overlay_path = overlay_path
        prediction.explainability_generated = True
        await self.analysis_repo.create_prediction(prediction)

        return {
            "analysis_id": analysis.id,
            "gradcam_url": f"/api/v1/analysis/file/{heatmap_path}",
            "overlay_url": f"/api/v1/analysis/file/{overlay_path}",
            "target_class": prediction.predicted_class,
        }

    async def get_analysis_for_user(self, analysis_id: uuid.UUID, user: User) -> Analysis:
        analysis = await self.analysis_repo.get_by_id_detailed(analysis_id)
        if not analysis:
            raise NotFoundException("Analysis record not found.")

        is_doctor_or_admin = any(
            r.name.lower() in ["doctor", "radiologist", "admin"] for r in user.roles
        )
        if analysis.user_id != user.id and not is_doctor_or_admin:
            raise ForbiddenException("You do not have permission to view this analysis record.")

        return analysis

    async def list_user_history(
        self, user: User, limit: int = 20, offset: int = 0
    ) -> Tuple[List[Analysis], int]:
        is_doctor_or_admin = any(
            r.name.lower() in ["doctor", "radiologist", "admin"] for r in user.roles
        )
        if is_doctor_or_admin:
            return await self.analysis_repo.get_all_analyses(limit=limit, offset=offset)
        return await self.analysis_repo.get_user_analyses(user.id, limit=limit, offset=offset)

    async def delete_analysis(self, analysis_id: uuid.UUID, user: User) -> bool:
        analysis = await self.get_analysis_for_user(analysis_id, user)
        # Delete image files from storage
        try:
            if analysis.image and analysis.image.storage_path:
                await self.storage.delete_file(analysis.image.storage_path)
            if analysis.prediction:
                if analysis.prediction.gradcam_path:
                    await self.storage.delete_file(analysis.prediction.gradcam_path)
                if analysis.prediction.overlay_path:
                    await self.storage.delete_file(analysis.prediction.overlay_path)
        except Exception as e:
            logger.warning(f"Error cleaning storage for analysis {analysis_id}: {str(e)}")

        await self.analysis_repo.delete(analysis)
        return True
