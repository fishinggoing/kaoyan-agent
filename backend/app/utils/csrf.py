"""Double-submit cookie CSRF protection.

Generates a random token, sets it as a cookie, and returns it to the client.
The client must send it back as X-CSRF-Token header on mutating requests.
The auth middleware compares cookie value === header value (constant-time).
"""

import secrets
import time
import logging

from fastapi import Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"
TOKEN_BYTES = 32
TOKEN_MAX_AGE = 60 * 60 * 24  # 24 hours


def generate_csrf_token() -> str:
    return secrets.token_hex(TOKEN_BYTES)


def set_csrf_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=CSRF_COOKIE,
        value=token,
        max_age=TOKEN_MAX_AGE,
        path="/",
        samesite="strict",
        httponly=False,  # JS doesn't read it; browser sends it automatically
        secure=False,    # set True once TLS is configured
    )


def get_csrf_cookie(request: Request) -> str:
    return request.cookies.get(CSRF_COOKIE, "")


def get_csrf_header(request: Request) -> str:
    return request.headers.get(CSRF_HEADER, "")


def validate_csrf(request: Request) -> bool:
    cookie_val = get_csrf_cookie(request)
    header_val = get_csrf_header(request)
    if not cookie_val or not header_val:
        return False
    return secrets.compare_digest(cookie_val, header_val)


def csrf_token_endpoint(request: Request, response: Response):
    token = generate_csrf_token()
    set_csrf_cookie(response, token)
    logger.debug("CSRF token issued for %s", request.client.host if request.client else "unknown")
    return {"success": True, "data": {"csrf_token": token}, "error": None}
