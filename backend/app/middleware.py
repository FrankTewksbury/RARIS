"""Request logging middleware with correlation IDs, timing, and rate limiting."""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings

logger = logging.getLogger("raris.access")

# Paths exempt from rate limiting
_EXEMPT_PATHS = {"/health", "/health/ready", "/docs", "/openapi.json", "/redoc"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Adds correlation ID, logs request timing, rate limiting, and sets response headers."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        start = time.monotonic()

        # Store correlation ID in request state
        request.state.correlation_id = correlation_id

        # Rate limiting (skip health checks and docs)
        rate_result = None
        if settings.rate_limit_rpm > 0 and request.url.path not in _EXEMPT_PATHS:
            from app.rate_limit import check_rate_limit

            # Use API key prefix if present, otherwise client IP
            api_key = request.headers.get("X-API-Key", "")
            if api_key:
                identifier = api_key[:12]
            else:
                identifier = request.client.host if request.client else "unknown"

            rate_result = await check_rate_limit(identifier)

            if not rate_result.allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"},
                    headers={
                        "X-Correlation-ID": correlation_id,
                        "X-RateLimit-Limit": str(rate_result.limit),
                        "X-RateLimit-Remaining": "0",
                        "Retry-After": str(int(rate_result.retry_after) + 1),
                    },
                )

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

        # Rate limit headers
        if rate_result:
            response.headers["X-RateLimit-Limit"] = str(rate_result.limit)
            response.headers["X-RateLimit-Remaining"] = str(rate_result.remaining)

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
