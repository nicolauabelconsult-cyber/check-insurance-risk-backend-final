import time, uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        request.state.req_id = uuid.uuid4().hex[:12]
        start = time.time()
        resp: Response = await call_next(request)
        dur_ms = int((time.time() - start) * 1000)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("Strict-Transport-Security","max-age=31536000; includeSubDomains; preload")
        resp.headers.setdefault("X-Request-ID", request.state.req_id)
        resp.headers.setdefault("Server-Timing", f"app;dur={dur_ms}")
        return resp
