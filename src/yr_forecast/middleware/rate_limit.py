"""Rate limiting middleware."""

import logging
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from yr_forecast.config import RATE_LIMIT_ENABLED
from yr_forecast.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware to enforce global rate limiting.

    Intercepts requests and checks if they should be allowed based on
    the configured rate limit. Returns HTTP 429 when limit exceeded.
    """

    # Paths that should bypass rate limiting
    BYPASS_PATHS = {
        "/health",
        "/info",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
    }

    def __init__(self, app, calls: int = 20):
        """Initialize rate limit middleware.

        Args:
            app: FastAPI application instance
            calls: Maximum requests per second (overrides config if provided)
        """
        super().__init__(app)
        self.rate_limiter = RateLimiter()
        self.enabled = RATE_LIMIT_ENABLED
        logger.info(f"Rate limit enabled: {self.enabled}, limit: {calls} req/sec")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through rate limiting check.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/endpoint in chain

        Returns:
            HTTP response (either rate limit error or continued response)
        """
        # Skip rate limiting for bypass paths
        if request.url.path in self.BYPASS_PATHS:
            return await call_next(request)

        # Skip if rate limiting is disabled
        if not self.enabled:
            return await call_next(request)

        # Check rate limit
        is_allowed, retry_after = await self.rate_limiter.is_allowed()

        if not is_allowed:
            request_host = {request.client.host if request.client else 'unknown'}
            endpoint = f"{request.method} {request.url.path}"
            logger.warning(f"Rate limit exceeded for {request_host} accessing {endpoint}")

            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please try again later.",
                    "retry_after": retry_after
                },
                headers={"Retry-After": str(retry_after)}
            )

        # Process request normally
        response = await call_next(request)

        # Add rate limit headers to response for transparency
        response.headers["X-RateLimit-Limit"] = str(self.rate_limiter.max_requests)
        response.headers["X-RateLimit-Window"] = "1"

        return response