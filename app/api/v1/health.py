from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.redis import get_redis_client
from app.ml.predictor import model_service
from app.storage.factory import get_storage_backend

router = APIRouter(prefix="/health", tags=["Health Checks"])


@router.get(
    "",
    summary="General System Health Check",
)
async def general_health(db: AsyncSession = Depends(get_db)):
    db_status = "unhealthy"
    try:
        await db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        pass

    redis_status = "unhealthy"
    try:
        r = await get_redis_client()
        if await r.ping():
            redis_status = "healthy"
    except Exception:
        pass

    ml_status = "loaded" if model_service.health_check() else "unavailable"

    overall = (
        "healthy"
        if db_status == "healthy" and redis_status == "healthy" and ml_status == "loaded"
        else "degraded"
    )

    return {
        "status": overall,
        "database": db_status,
        "redis": redis_status,
        "ml_model": ml_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/database", summary="Database Connection Health")
async def db_health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "healthy", "service": "PostgreSQL"}
    except Exception as e:
        return {"status": "unhealthy", "service": "PostgreSQL", "error": str(e)}


@router.get("/redis", summary="Redis Connection Health")
async def redis_health():
    try:
        r = await get_redis_client()
        pong = await r.ping()
        return {"status": "healthy" if pong else "unhealthy", "service": "Redis"}
    except Exception as e:
        return {"status": "unhealthy", "service": "Redis", "error": str(e)}


@router.get("/ml-model", summary="ML Inference Model Health")
async def ml_model_health():
    is_healthy = model_service.health_check()
    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "service": "PyTorch Brain MRI Classifier",
        "model_version": model_service.loader.model_version,
    }
