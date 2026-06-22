from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import router as api_router
from app.config import settings
from app.db.database import engine, Base
from app.utils.exceptions import AppException
from app.utils.logging import setup_logging
from app.middleware.auth import ApiKeyMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.utils.csrf import csrf_token_endpoint


def _validate_config():
    """Validate critical configuration at startup (moved from import time)."""
    import logging
    logger = logging.getLogger(__name__)
    if not settings.deepseek_api_key:
        logger.error(
            "DEEPSEEK_API_KEY is not set — AI features (decisions, needs-analysis) will fail"
        )
    if not settings.api_key:
        logger.error(
            "API_KEY is not set — protected endpoints (decisions, needs-analysis, "
            "profiles, score-cards) will return 503. "
            "Set API_KEY in .env or environment variable."
        )
    else:
        if len(settings.api_key) < 16:
            logger.warning(
                "API_KEY is weak (< 16 characters). Generate a strong key: "
                "openssl rand -hex 32"
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    _validate_config()
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="GradSchool Advisor",
    description="考研院校与专业智能决策辅助系统",
    version="0.1.0",
    lifespan=lifespan,
)


# Security headers middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

        # HSTS: only send over HTTPS (avoids poisoning localhost/dev browsers)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        if settings.debug:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self' https://api.deepseek.com; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )
        else:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self' https://api.deepseek.com; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response


app.add_middleware(SecurityHeadersMiddleware)

# CORS — read from config (comma-separated), reject wildcard
origins = [o.strip() for o in settings.allow_origins.split(",") if o.strip()]
if "*" in origins:
    raise ValueError(
        "ALLOW_ORIGINS must not contain '*' when allow_credentials=True. "
        "Use specific origins instead."
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key", "X-Client-ID"],
)

# Rate limiting (LLM endpoints + write operations)
app.add_middleware(RateLimitMiddleware)

# API Key authentication (write + LLM endpoints)
app.add_middleware(ApiKeyMiddleware)

# ── Request body size limit (1 MB) ──────────────────────────────────────
MAX_BODY_SIZE = 1 * 1024 * 1024  # 1 MB

@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_BODY_SIZE:
                return JSONResponse(
                    {"success": False, "data": None, "error": "Request body too large (max 1 MB)"},
                    status_code=413,
                )
        except ValueError:
            pass
    return await call_next(request)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.code,
        content={"success": False, "data": None, "error": exc.message},
    )


@app.get("/api/health")
async def health_check():
    return {"success": True, "data": {"status": "healthy", "version": "0.1.0"}, "error": None}


@app.get("/api/csrf-token")
async def get_csrf_token(request: Request, response: Response):
    """Issue a CSRF token (double-submit cookie) for the SPA frontend."""
    return csrf_token_endpoint(request, response)


app.include_router(api_router, prefix="/api")

# ── Production: serve frontend static files ──────────────────────────────
static_dir = settings.static_dir.strip()
if static_dir:
    static_path = Path(static_dir)
    if static_path.is_dir():
        app.mount("/assets", StaticFiles(directory=str(static_path / "assets")), name="assets")

        @app.get("/")
        async def serve_root():
            index = static_path / "index.html"
            if index.is_file():
                return FileResponse(str(index))
            return JSONResponse(
                {"success": False, "data": None, "error": "Not found"}, status_code=404
            )

        @app.get("/{full_path:path}")
        async def serve_spa(request: Request, full_path: str):
            # API routes without trailing slash: redirect so FastAPI can match them
            if full_path.startswith("api/"):
                if not request.url.path.endswith("/"):
                    return RedirectResponse(url=request.url.path + "/", status_code=307)
                return JSONResponse(
                    {"success": False, "data": None, "error": "Not found"}, status_code=404
                )
            # Normalize path to prevent path traversal
            resolved = (static_path / full_path).resolve()
            if not str(resolved).startswith(str(static_path.resolve())):
                return JSONResponse(
                    {"success": False, "data": None, "error": "Not found"}, status_code=404
                )
            if resolved.is_file():
                return FileResponse(str(resolved))
            index = static_path / "index.html"
            if index.is_file():
                return FileResponse(str(index))
            return JSONResponse(
                {"success": False, "data": None, "error": "Not found"}, status_code=404
            )
