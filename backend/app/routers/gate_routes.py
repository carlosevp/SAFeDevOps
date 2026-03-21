from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.access_gate import (
    COOKIE_MAX_AGE_SECONDS,
    COOKIE_NAME,
    cookie_secure_for_request,
    gate_enabled,
    issue_gate_cookie_value,
    passwords_match,
    request_has_valid_gate_cookie,
)

router = APIRouter(prefix="/api/auth", tags=["access"])


class GateStatusOut(BaseModel):
    gate_enabled: bool
    authenticated: bool


class GateLoginIn(BaseModel):
    password: str = Field(min_length=1, max_length=4096)


@router.get("/gate/status", response_model=GateStatusOut)
def gate_status(request: Request) -> GateStatusOut:
    enabled = gate_enabled()
    return GateStatusOut(
        gate_enabled=enabled,
        authenticated=not enabled or request_has_valid_gate_cookie(request),
    )


@router.post("/gate/login")
def gate_login(request: Request, body: GateLoginIn, response: Response) -> dict[str, bool]:
    if not gate_enabled():
        return {"ok": True}
    if passwords_match(body.password):
        token = issue_gate_cookie_value()
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            max_age=COOKIE_MAX_AGE_SECONDS,
            httponly=True,
            secure=cookie_secure_for_request(request),
            samesite="lax",
            path="/",
        )
        return {"ok": True}
    raise HTTPException(status_code=401, detail="Incorrect password.")


@router.post("/gate/logout")
def gate_logout(request: Request, response: Response) -> dict[str, bool]:
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        secure=cookie_secure_for_request(request),
        httponly=True,
        samesite="lax",
    )
    return {"ok": True}
