from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import api_v1_router
from app.api.v1.health import router as health_router
from app.core.config import settings
from app.core.database import Base, engine
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    generic_exception_handler,
    validation_exception_handler,
)
from app.core.logging import logger, setup_logging
from app.core.middleware import RequestTracingMiddleware, setup_metrics_endpoint
from app.core.redis import close_redis_client, get_redis_client
from app.ml.predictor import model_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for application startup and shutdown events."""
    # 1. Setup structured logging
    setup_logging()
    logger.info("Initializing Medical Brain MRI Analysis Backend...")

    # 2. Pre-load and warm up PyTorch Deep Learning Model
    try:
        model_service.load_model()
        logger.info("ML Inference Engine initialized successfully.")
    except Exception as e:
        logger.warning(f"ML Model initialization warning (will retry on demand): {str(e)}")

    # 3. Create database tables if in development
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema verified.")
    except Exception as e:
        logger.error(f"Database connection error on startup: {str(e)}")

    # 4. Initialize Redis
    try:
        r = await get_redis_client()
        await r.ping()
        logger.info("Redis cache connection established.")
    except Exception as e:
        logger.warning(f"Redis not available on startup: {str(e)}")

    yield

    # Shutdown
    logger.info("Shutting down application...")
    await close_redis_client()
    await engine.dispose()
    logger.info("Application shutdown complete.")


def create_app() -> FastAPI:
    """Application factory for FastAPI app."""
    app = FastAPI(
        title="Medical Brain MRI Image Analysis & Screening API",
        description=(
            "### AI-Assisted Clinical Decision-Support Platform for Brain MRI Analysis\n\n"
            "**Medical Disclaimer:** All AI outputs produced by this system represent preliminary screening "
            "predictions and do NOT constitute confirmed medical diagnoses. Predictions must always be verified "
            "by certified radiologists or qualified healthcare professionals."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Setup Prometheus /metrics
    if settings.ENABLE_PROMETHEUS_METRICS:
        setup_metrics_endpoint(app)

    # Middleware setup (Tracing & CORS)
    app.add_middleware(RequestTracingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS if isinstance(settings.ALLOWED_ORIGINS, list) else [settings.ALLOWED_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception Handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Mount API Routers
    app.include_router(api_v1_router, prefix=settings.API_V1_STR)
    app.include_router(health_router)

    @app.get("/", include_in_schema=False)
    def root():
        return {
            "name": settings.APP_NAME,
            "version": "1.0.0",
            "environment": settings.APP_ENV,
            "docs": "/docs",
            "health": "/health",
        }

    return app


app = create_app()
