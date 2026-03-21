"""Require access cookie for API and static assets when SAFEDEVOPS_ACCESS_PASSWORD is set."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.access_gate import gate_enabled, request_has_valid_gate_cookie


class AccessGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not gate_enabled():
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        if path.startswith("/api/health"):
            return await call_next(request)
        if path.startswith("/api/auth/gate/"):
            return await call_next(request)

        if path.startswith("/api/"):
            if not request_has_valid_gate_cookie(request):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Authentication required."},
                )
            return await call_next(request)

        if path.startswith("/assets/"):
            if not request_has_valid_gate_cookie(request):
                return Response(status_code=401)
            return await call_next(request)

        if path in ("/docs", "/redoc", "/openapi.json"):
            if not request_has_valid_gate_cookie(request):
                return Response(status_code=401)
            return await call_next(request)

        if path != "/" and path.count("/") <= 1 and "." in path.split("/")[-1]:
            if not request_has_valid_gate_cookie(request):
                return Response(status_code=401)
            return await call_next(request)

        return await call_next(request)
