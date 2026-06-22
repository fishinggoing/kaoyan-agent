"""Authentication middleware — CSRF double-submit cookie + API Key.

For browser (same-origin SPA) requests:
  - A CSRF token cookie is set by GET /api/csrf-token on first load.
  - The frontend sends it back as X-CSRF-Token header on mutating requests.
  - The middleware compares cookie value === header value (constant-time).
  - This prevents CSRF because an attacker cannot read the cookie (SameSite=Strict)
    nor set the custom header cross-origin.

For external API clients (curl, scripts, other servers):
  - Send X-API-Key header with the configured API_KEY value.
  - CSRF cookie is NOT required when a valid X-API-Key is present.
"""

import logging
import secrets
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.utils.csrf import validate_csrf

logger = logging.getLogger(__name__)

# Paths that don't require authentication
PUBLIC_PATHS = {
    "/api/health",
    "/api/docs",
    "/api/openapi.json",
    "/api/redoc",
    "/api/csrf-token",
}

# Paths that require authentication (write operations + LLM calls)
PROTECTED_PREFIXES = (
    "/api/decisions/",
    "/api/needs-analysis/",
    "/api/profiles/",
    "/api/score-cards/",
)


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Authenticate protected endpoints via CSRF cookie or X-API-Key header.

    Two authentication paths:
      1. CSRF double-submit cookie (for the SPA frontend served by this server)
      2. X-API-Key header (for external API clients)

    If neither API_KEY nor CSRF is configured/valid, the middleware rejects
    with 403 or 503 as appropriate.
    """

    async def dispatch(self, request: Request, call_next):
        # CORS preflight — browsers don't send custom headers on OPTIONS
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        # Skip public endpoints
        if path in PUBLIC_PATHS:
            return await call_next(request)

        # Only protect write/LLM endpoints
        if not path.startswith(PROTECTED_PREFIXES):
            return await call_next(request)

        # ── Authentication gate ──────────────────────────────────────
        # Check X-API-Key first (external API clients)
        if settings.api_key:
            client_key = request.headers.get("X-API-Key", "")
            if secrets.compare_digest(client_key, settings.api_key):
                return await call_next(request)

        # Check CSRF double-submit cookie (SPA frontend)
        if validate_csrf(request):
            return await call_next(request)

        # Both failed — reject
        if not settings.api_key:
            logger.error(
                "API_KEY not configured — rejecting request to %s. "
                "Set API_KEY in .env or environment variable.",
                path,
            )
            return JSONResponse(
                {
                    "success": False,
                    "data": None,
                    "error": "Server authentication is not configured. Please set API_KEY.",
                },
                status_code=503,
            )

        return JSONResponse(
            {"success": False, "data": None, "error": "Invalid or missing authentication"},
            status_code=403,
        )
