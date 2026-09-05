import os
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "medical_brain_mri_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.worker_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes maximum for heavy MRI slice processing
    worker_prefetch_multiplier=1,
)
