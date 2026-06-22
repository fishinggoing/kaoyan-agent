"""Simple in-memory rate limiter middleware.

For single-process deployments. Each worker maintains independent counters,
so with multiple uvicorn workers (--workers N where N > 1) the effective
limit is N × configured_max.  For multi-worker deployments, replace with
a shared store (Redis, memcached) or use Nginx rate limiting as the
primary mechanism (see deploy checklist).
"""

import logging
import time
from collections import defaultdict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Window in seconds and max requests per window
LLM_RATE_LIMIT = (60, 10)        # 10 requests per minute for LLM endpoints
WRITE_RATE_LIMIT = (60, 30)      # 30 requests per minute for write endpoints

# In-memory store: {client_ip: [(timestamp, path), ...]}
_llm_hits: dict[str, list[float]] = defaultdict(list)
_write_hits: dict[str, list[float]] = defaultdict(list)

# Track last cleanup time to avoid scanning on every request
_last_cleanup = time.monotonic()
CLEANUP_INTERVAL = 300  # 5 minutes between dead-entry sweeps

LLM_PREFIXES = (
    "/api/decisions/",
    "/api/needs-analysis/",
)

WRITE_METHODS = {"POST", "PUT", "DELETE"}

# Warn if imported in a multi-worker context (heuristic: check common env vars)
_worker_count = 1
try:
    import os
    _workers = os.environ.get("UVICORN_WORKERS", os.environ.get("WEB_CONCURRENCY", "1"))
    _worker_count = int(_workers)
except (ValueError, TypeError):
    pass
if _worker_count > 1:
    logger.warning(
        "Detected %s workers — in-memory rate limiter counters are per-worker. "
        "Effective limits are %s× the configured values. Use Redis or Nginx instead.",
        _worker_count, _worker_count,
    )


def _clean_window(hits: list[float], window: float) -> list[float]:
    """Remove timestamps outside the current window."""
    cutoff = time.monotonic() - window
    return [t for t in hits if t > cutoff]


def _sweep_dead_entries():
    """Periodically remove entries whose timestamp lists are empty."""
    global _last_cleanup
    now = time.monotonic()
    if now - _last_cleanup < CLEANUP_INTERVAL:
        return
    _last_cleanup = now

    for store in (_llm_hits, _write_hits):
        dead_keys = [k for k, v in store.items() if not v]
        for k in dead_keys:
            del store[k]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply per-IP rate limits to expensive endpoints."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method
        client_ip = request.client.host if request.client else "unknown"

        now = time.monotonic()

        # LLM endpoints — stricter limit
        if path.startswith(LLM_PREFIXES):
            window, max_req = LLM_RATE_LIMIT
            hits = _llm_hits[client_ip]
            hits = _clean_window(hits, window)
            _llm_hits[client_ip] = hits

            if len(hits) >= max_req:
                raise HTTPException(
                    status_code=429,
                    detail=f"LLM API rate limit exceeded ({max_req} per {window}s). Please wait.",
                )
            hits.append(now)
            _sweep_dead_entries()
            return await call_next(request)

        # Write endpoints — moderate limit
        if method in WRITE_METHODS:
            window, max_req = WRITE_RATE_LIMIT
            hits = _write_hits[client_ip]
            hits = _clean_window(hits, window)
            _write_hits[client_ip] = hits

            if len(hits) >= max_req:
                raise HTTPException(
                    status_code=429,
                    detail=f"Write rate limit exceeded ({max_req} per {window}s). Please wait.",
                )
            hits.append(now)
            _sweep_dead_entries()

        return await call_next(request)
