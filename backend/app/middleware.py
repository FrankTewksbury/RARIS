"""Request logging middleware with correlation IDs and timing."""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("raris.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Adds correlation ID, logs request timing, and sets response headers."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        start = time.monotonic()

        # Store correlation ID in request state
        request.state.correlation_id = correlation_id

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.monotonic() - start) * 1000
            logger.error(
                "%s %s 500 %.1fms [%s]",
                request.method,
                request.url.path,
                duration_ms,
                correlation_id,
            )
            raise

        duration_ms = (time.monotonic() - start) * 1000

        # Set response headers
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.1f}"

        # Log the request
        logger.info(
            "%s %s %d %.1fms [%s]",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            correlation_id,
        )

        return response
