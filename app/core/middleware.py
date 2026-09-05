import time
import uuid
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from app.core.logging import logger

# Prometheus Metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests received",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

PREDICTION_COUNT = Counter(
    "ml_predictions_total",
    "Total ML predictions executed",
    ["model_version", "predicted_class", "status"],
)

PREDICTION_LATENCY = Histogram(
    "ml_prediction_duration_seconds",
    "ML prediction inference latency in seconds",
    ["model_version"],
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0],
)


class RequestTracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        start_time = time.time()
        
        try:
            response: Response = await call_next(request)
            process_time = time.time() - start_time
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.4f}s"

            # Log request metrics
            endpoint = request.url.path
            method = request.method
            status_code = str(response.status_code)

            if not endpoint.startswith(("/metrics", "/health")):
                REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
                REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(process_time)
                
                logger.info(
                    "Request processed",
                    extra={
                        "request_id": request_id,
                        "method": method,
                        "endpoint": endpoint,
                        "status_code": response.status_code,
                        "duration_ms": round(process_time * 1000, 2),
                    },
                )
            return response
        except Exception as exc:
            process_time = time.time() - start_time
            logger.error(
                "Request unhandled exception",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "endpoint": request.url.path,
                    "error": str(exc),
                    "duration_ms": round(process_time * 1000, 2),
                },
            )
            raise exc


def setup_metrics_endpoint(app: FastAPI):
    """Register /metrics endpoint for Prometheus scrapers."""
    @app.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
