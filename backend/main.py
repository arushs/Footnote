import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.db import init_db
from app.middleware import RequestSizeLimitMiddleware, limiter
from app.routes import auth, chat, folders, health
from app.services.anthropic import close_client as close_anthropic_client
from app.services.posthog import shutdown_posthog

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """Validate Origin header for state-changing requests to prevent CSRF."""

    async def dispatch(self, request: Request, call_next):
        # Only check state-changing methods
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            origin = request.headers.get("origin")
            # Allow requests without Origin (same-origin, non-browser)
            if origin and origin not in settings.cors_origins:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF validation failed: invalid origin"},
                )
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown - cleanup SDK clients
    await close_anthropic_client()
    shutdown_posthog()


app = FastAPI(
    title="Footnote API",
    description="RAG API for chatting with Google Drive folders",
    version="0.1.0",
    lifespan=lifespan,
)

# Rate limiter state (required by slowapi)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Request size limit middleware (prevents memory exhaustion)
app.add_middleware(RequestSizeLimitMiddleware)

# CSRF protection - validates Origin header for state-changing requests
app.add_middleware(CSRFProtectionMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(folders.router, prefix="/api/folders", tags=["folders"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(health.router, prefix="/api/health", tags=["health"])
