import logging
import time
import uuid
from fastapi import Request

logger = logging.getLogger("faresniper.request")


async def record_latency(request: Request, call_next):
    t0 = time.monotonic()
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.exception(
            "request_failed request_id=%s method=%s path=%s duration_ms=%s",
            request_id,
            request.method,
            request.url.path,
            duration_ms,
        )
        raise

    duration_ms = int((time.monotonic() - t0) * 1000)
    response.headers["x-latency-ms"] = str(duration_ms)
    response.headers["x-request-id"] = request_id
    if response.status_code >= 500:
        logger.error(
            "request_5xx request_id=%s method=%s path=%s status=%s duration_ms=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
    return response
