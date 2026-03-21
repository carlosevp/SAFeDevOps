"""Require access cookie for API and static assets when SAFEDEVOPS_ACCESS_PASSWORD is set."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.access_gate import gate_enabled, request_has_valid_gate_cookie

_UNAUTH_API = JSONResponse(status_code=401, content={"detail": "Authentication required."})
_UNAUTH_PLAIN = Response(status_code=401)


def _public_without_cookie(path: str) -> bool:
    return path.startswith("/api/health") or path.startswith("/api/auth/gate/")


def _is_root_level_static_file(path: str) -> bool:
    return path != "/" and path.count("/") <= 1 and "." in path.split("/")[-1]


class AccessGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not gate_enabled() or request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if _public_without_cookie(path):
            return await call_next(request)

        if path.startswith("/api/"):
            return await self._next_or(request, call_next, json401=True)
        if path.startswith("/assets/"):
            return await self._next_or(request, call_next, json401=False)
        if path in ("/docs", "/redoc", "/openapi.json"):
            return await self._next_or(request, call_next, json401=False)
        if _is_root_level_static_file(path):
            return await self._next_or(request, call_next, json401=False)

        return await call_next(request)

    async def _next_or(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
        *,
        json401: bool,
    ) -> Response:
        if request_has_valid_gate_cookie(request):
            return await call_next(request)
        return _UNAUTH_API if json401 else _UNAUTH_PLAIN
