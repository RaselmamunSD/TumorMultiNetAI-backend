import logging
import sys
from pythonjsonlogger import jsonlogger
from app.core.config import settings


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        log_record["app"] = settings.APP_NAME
        log_record["environment"] = settings.APP_ENV
        log_record["level"] = record.levelname
        
        # Ensure sensitive fields are never leaked
        for sensitive_key in ["password", "token", "image_bytes", "pixel_array", "authorization"]:
            if sensitive_key in log_record:
                log_record[sensitive_key] = "[REDACTED]"


def setup_logging():
    """Setup structured JSON logger for production observability."""
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # Remove existing handlers
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    formatter = CustomJsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Set external libraries log levels to reduce noise
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("pydicom").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    
    return logger


logger = logging.getLogger("medical_backend")
