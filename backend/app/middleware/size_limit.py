"""Request body size limit middleware."""

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings

logger = logging.getLogger(__name__)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce maximum request body size.

    Prevents memory exhaustion from oversized payloads by checking
    Content-Length header before reading the body.
    """

    def __init__(self, app, max_size: int | None = None):
        super().__init__(app)
        self.max_size = max_size or settings.max_request_size_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")

        if content_length:
            try:
                size = int(content_length)
                if size > self.max_size:
                    logger.warning(
                        f"Request body too large: {size} bytes (max: {self.max_size})",
                        extra={
                            "content_length": size,
                            "max_size": self.max_size,
                            "path": request.url.path,
                            "method": request.method,
                        },
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": f"Request body exceeds maximum size of {self.max_size} bytes"
                        },
                    )
            except ValueError:
                # Invalid content-length header - let downstream handle it
                pass

        return await call_next(request)
