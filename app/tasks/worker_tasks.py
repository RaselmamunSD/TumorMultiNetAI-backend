import asyncio
import time
import uuid
from app.tasks.celery_app import celery_app
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging import logger
from app.models.analysis import Analysis, AnalysisStatus, Prediction
from app.ml.predictor import model_service
from app.repositories.analysis_repo import AnalysisRepository
from app.storage.factory import get_storage_backend


def run_async(coro):
    """Utility to run asynchronous coroutine inside synchronous Celery worker."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name="process_mri_analysis_task")
def process_mri_analysis_task(self, analysis_id_str: str):
    """
    Celery background task for asynchronous deep learning brain MRI analysis.
    """
    analysis_id = uuid.UUID(analysis_id_str)
    logger.info(f"Celery task starting for analysis ID: {analysis_id}")

    async def _execute():
        async with AsyncSessionLocal() as db:
            repo = AnalysisRepository(db)
            storage = get_storage_backend()

            analysis = await repo.get_by_id_detailed(analysis_id)
            if not analysis:
                logger.error(f"Analysis {analysis_id} not found in worker task.")
                return

            analysis.status = AnalysisStatus.PROCESSING
            analysis.progress_percentage = 30
            await repo.update(analysis)

            start_time = time.time()
            try:
                # Read image file bytes from storage
                file_bytes = await storage.read_file(analysis.image.storage_path)

                analysis.progress_percentage = 60
                await repo.update(analysis)

                # Execute PyTorch inference
                ml_result = model_service.predict(file_bytes, analysis.image.file_name)
                elapsed_ms = round((time.time() - start_time) * 1000, 2)

                # Persist prediction result
                prediction = Prediction(
                    analysis_id=analysis.id,
                    model_name=ml_result.get("model_name", "BrainMRIClassifier"),
                    model_version=ml_result.get("model_version", settings.MODEL_VERSION),
                    predicted_class=ml_result["predicted_class"],
                    screening_label=ml_result["screening_label"],
                    confidence=ml_result["confidence"],
                    is_abnormal=ml_result["is_abnormal"],
                    probabilities=ml_result["probabilities"],
                    inference_time_ms=ml_result.get("inference_time_ms", elapsed_ms),
                    disclaimer=ml_result["disclaimer"],
                )
                await repo.create_prediction(prediction)

                analysis.status = AnalysisStatus.COMPLETED
                analysis.progress_percentage = 100
                analysis.processing_time_ms = elapsed_ms
                await repo.update(analysis)

                logger.info(f"Analysis {analysis_id} completed successfully in {elapsed_ms}ms.")

            except Exception as e:
                logger.error(f"Analysis {analysis_id} failed in worker: {str(e)}")
                analysis.status = AnalysisStatus.FAILED
                analysis.error_message = str(e)
                analysis.progress_percentage = 0
                await repo.update(analysis)
                raise e

    return run_async(_execute())


@celery_app.task(bind=True, name="generate_explainability_task")
def generate_explainability_task(self, analysis_id_str: str):
    """
    Celery background task for generating Grad-CAM heatmaps and overlays.
    """
    analysis_id = uuid.UUID(analysis_id_str)

    async def _execute():
        async with AsyncSessionLocal() as db:
            repo = AnalysisRepository(db)
            storage = get_storage_backend()

            analysis = await repo.get_by_id_detailed(analysis_id)
            if not analysis or not analysis.prediction:
                return

            file_bytes = await storage.read_file(analysis.image.storage_path)
            heatmap_bytes, overlay_bytes, _ = model_service.explain(
                image_bytes=file_bytes,
                filename=analysis.image.file_name,
            )

            subfolder = f"explainability/{analysis.user_id}"
            heatmap_name = f"gradcam_heatmap_{analysis.id}.png"
            overlay_name = f"gradcam_overlay_{analysis.id}.png"

            heatmap_path = await storage.save_file(heatmap_bytes, heatmap_name, subfolder)
            overlay_path = await storage.save_file(overlay_bytes, overlay_name, subfolder)

            prediction = analysis.prediction
            prediction.gradcam_path = heatmap_path
            prediction.overlay_path = overlay_path
            prediction.explainability_generated = True
            await repo.create_prediction(prediction)

    return run_async(_execute())
