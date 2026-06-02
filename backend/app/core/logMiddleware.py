import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.loggingConfig import request_id_var

logger = logging.getLogger("http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = uuid.uuid4().hex[:8]
        token = request_id_var.set(req_id)
        start = time.perf_counter()

        logger.info(
            "request_start method=%s path=%s",
            request.method,
            request.url.path,
        )

        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            logger.exception("request_error method=%s path=%s", request.method, request.url.path)
            raise
        finally:
            elapsed_ms = round((time.perf_counter() - start) * 1000)
            logger.info(
                "request_end method=%s path=%s status=%d elapsed_ms=%d",
                request.method,
                request.url.path,
                status_code,
                elapsed_ms,
            )
            request_id_var.reset(token)
