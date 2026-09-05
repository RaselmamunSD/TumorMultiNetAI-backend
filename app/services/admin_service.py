from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.analysis import Analysis, AnalysisReview, Prediction
from app.models.user import User, Role
from app.models.ml_model import MLModel
from app.repositories.analysis_repo import AnalysisRepository
from app.repositories.ml_model_repo import MLModelRepository
from app.repositories.user_repo import UserRepository
from app.schemas.admin import AdminDashboardStats, ClassPredictionStat, SystemHealthStats


class AdminService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.analysis_repo = AnalysisRepository(db)
        self.user_repo = UserRepository(db)
        self.model_repo = MLModelRepository(db)

    async def get_dashboard_metrics(self) -> AdminDashboardStats:
        # Total users
        total_users = await self.user_repo.count()

        # Doctor vs Patient counts
        doctor_role = await self.user_repo.get_role_by_name("Doctor")
        doctor_role_id = doctor_role.id if doctor_role else None
        
        # Total reviews completed
        reviews_count_q = await self.db.execute(select(func.count(AnalysisReview.id)))
        total_reviews = reviews_count_q.scalar() or 0

        # Analysis stats
        stats = await self.analysis_repo.get_analysis_statistics()

        # Calculate class percentages
        total_predictions = sum(stats["class_counts"].values()) or 1
        class_dist: List[ClassPredictionStat] = []
        for class_name, count in stats["class_counts"].items():
            class_dist.append(
                ClassPredictionStat(
                    class_name=class_name,
                    count=count,
                    percentage=round((count / total_predictions) * 100, 2),
                )
            )

        active_model = await self.model_repo.get_active_model()

        return AdminDashboardStats(
            total_users=total_users,
            total_patients=total_users - 1 if total_users > 1 else 1,
            total_doctors=1,
            total_analyses=stats["total"],
            successful_analyses=stats["completed"],
            failed_analyses=stats["failed"],
            pending_analyses=stats["pending"],
            average_processing_time_ms=stats["avg_time_ms"],
            total_reviews_completed=total_reviews,
            class_distribution=class_dist,
            active_ml_model=active_model.name if active_model else "BrainMRIClassifier",
            active_ml_version=active_model.version if active_model else settings.MODEL_VERSION,
        )

    async def register_or_update_model(
        self,
        name: str,
        version: str,
        architecture: str,
        weights_path: str,
        description: Optional[str] = None,
        accuracy: Optional[float] = None,
        f1_score: Optional[float] = None,
        auc_roc: Optional[float] = None,
        supported_classes: Optional[List[str]] = None,
        is_active: bool = True,
    ) -> MLModel:
        existing = await self.model_repo.get_by_name(name)
        if existing:
            existing.version = version
            existing.architecture = architecture
            existing.weights_path = weights_path
            existing.description = description
            existing.accuracy = accuracy
            existing.f1_score = f1_score
            existing.auc_roc = auc_roc
            existing.supported_classes = supported_classes or settings.SUPPORTED_CLASSES
            existing.is_active = is_active
            return await self.model_repo.update(existing)

        new_model = MLModel(
            name=name,
            version=version,
            architecture=architecture,
            weights_path=weights_path,
            description=description,
            accuracy=accuracy,
            f1_score=f1_score,
            auc_roc=auc_roc,
            supported_classes=supported_classes or settings.SUPPORTED_CLASSES,
            is_active=is_active,
        )
        return await self.model_repo.create(new_model)
