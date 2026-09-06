import os
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # General Application Settings
    APP_NAME: str = "Medical Brain MRI Analysis API"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Security & Tokens
    SECRET_KEY: str = "CHANGE_THIS_IN_PRODUCTION_SUPER_SECRET_KEY_MIN_32_CHARS"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # CORS
    ALLOWED_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:5173",
    ]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    RATE_LIMIT_PER_MINUTE: int = 100

    # PostgreSQL Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "brain_mri_db"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/brain_mri_db"
    DATABASE_SYNC_URL: str = "postgresql://postgres:postgres@localhost:5432/brain_mri_db"

    # Redis & Celery
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ML Model Configuration
    MODEL_DIR: str = "./models"
    MODEL_PATH: str = "./models/brain_mri_resnet50_v1.pt"
    MODEL_VERSION: str = "1.0.0"
    MODEL_DEVICE: str = "cpu"  # cpu, cuda, mps
    CONFIDENCE_THRESHOLD: float = 0.50
    SUPPORTED_CLASSES: List[str] = ["no_tumor", "glioma", "meningioma", "pituitary"]

    # Storage Settings
    STORAGE_BACKEND: str = "local"  # local, s3, minio
    LOCAL_STORAGE_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: List[str] = [".jpg", ".jpeg", ".png", ".dcm"]

    # S3 / MinIO / R2
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET: str = "medical-brain-mri-images"
    AWS_S3_ENDPOINT_URL: str = ""

    # Logging & Monitoring
    LOG_LEVEL: str = "INFO"
    ENABLE_PROMETHEUS_METRICS: bool = True

    # Gemini AI Configuration
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"

    # Medical Disclaimer Standard text
    MEDICAL_DISCLAIMER: str = (
        "This result is an AI-assisted screening prediction and is NOT a confirmed medical diagnosis. "
        "AI models may produce false positives or false negatives. All results must be reviewed and "
        "correlated with clinical findings by a qualified medical professional or certified radiologist."
    )


settings = Settings()
