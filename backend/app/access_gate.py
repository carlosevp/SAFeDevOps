"""Optional shared-password gate (Railway / single-host deployments)."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from itsdangerous import BadSignature, URLSafeTimedSerializer
from starlette.requests import Request

from app.settings import settings

COOKIE_NAME = "safedevops_gate"
COOKIE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60


def gate_enabled() -> bool:
    return bool(settings.safedevops_access_password)


def _password_fingerprint() -> str:
    p = settings.safedevops_access_password
    return hashlib.sha256(p.encode("utf-8")).hexdigest()


def _serializer() -> URLSafeTimedSerializer:
    key = hmac.new(
        b"safedevops-gate-cookie-v1",
        _password_fingerprint().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return URLSafeTimedSerializer(key, salt="safedevops-access-gate")


def issue_gate_cookie_value() -> str:
    return _serializer().dumps({"ok": True})


def gate_cookie_valid(token: str | None) -> bool:
    if not token or not gate_enabled():
        return False
    ser = _serializer()
    try:
        ser.loads(token, max_age=COOKIE_MAX_AGE_SECONDS)
        return True
    except (BadSignature, TypeError, ValueError):
        return False


def request_has_valid_gate_cookie(request: Request) -> bool:
    return gate_cookie_valid(request.cookies.get(COOKIE_NAME))


def passwords_match(provided: str) -> bool:
    if not gate_enabled():
        return True
    expected = settings.safedevops_access_password.encode("utf-8")
    given = provided.encode("utf-8")
    if len(given) > 4096:
        return False
    return secrets.compare_digest(
        hashlib.sha256(given).digest(),
        hashlib.sha256(expected).digest(),
    )


def cookie_secure_for_request(request: Request) -> bool:
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "").lower()
    return proto == "https"


LOGIN_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Sign in — SAFe DevOps assessment</title>
  <style>
    :root { color-scheme: light dark; }
    body { font-family: system-ui, -apple-system, Segoe UI, sans-serif; margin: 0; min-height: 100vh;
      display: flex; align-items: center; justify-content: center;
      background: #0f1419; color: #e8edf4; }
    @media (prefers-color-scheme: light) {
      body { background: #f4f6fb; color: #111827; }
    }
    .card { width: 100%; max-width: 380px; padding: 1.75rem; border-radius: 14px;
      background: rgba(26, 34, 45, 0.95); border: 1px solid #2d3a4d;
      box-shadow: 0 12px 48px rgba(0,0,0,0.35); }
    @media (prefers-color-scheme: light) {
      .card { background: #fff; border-color: #e2e8f0; box-shadow: 0 10px 40px rgba(15,23,42,0.07); }
    }
    h1 { font-size: 1.15rem; margin: 0 0 0.35rem; font-weight: 600; }
    p { margin: 0 0 1rem; font-size: 0.9rem; opacity: 0.85; }
    label { display: block; font-size: 0.8rem; margin-bottom: 0.35rem; opacity: 0.9; }
    input { width: 100%; padding: 0.65rem 0.75rem; border-radius: 10px; border: 1px solid #2d3a4d;
      background: #161d27; color: inherit; font-size: 1rem; box-sizing: border-box; }
    @media (prefers-color-scheme: light) {
      input { border-color: #e2e8f0; background: #fff; color: #111827; }
    }
    button { margin-top: 1rem; width: 100%; padding: 0.65rem 1rem; border: none; border-radius: 10px;
      font-size: 1rem; font-weight: 600; cursor: pointer; background: #60a5fa; color: #0f1419; }
    button:hover { filter: brightness(1.05); }
    button:disabled { opacity: 0.6; cursor: not-allowed; }
    .err { color: #f87171; font-size: 0.85rem; margin-top: 0.5rem; min-height: 1.2em; }
    @media (prefers-color-scheme: light) { .err { color: #b91c1c; } }
  </style>
</head>
<body>
  <div class="card">
    <h1>Access password</h1>
    <p>This deployment is protected. Enter the shared password to continue.</p>
    <form id="f" autocomplete="current-password">
      <label for="pw">Password</label>
      <input id="pw" name="password" type="password" required autofocus/>
      <div class="err" id="e" aria-live="polite"></div>
      <button type="submit" id="btn">Continue</button>
    </form>
  </div>
  <script>
    document.getElementById("f").addEventListener("submit", async function (ev) {
      ev.preventDefault();
      var btn = document.getElementById("btn");
      var err = document.getElementById("e");
      var pw = document.getElementById("pw").value;
      err.textContent = "";
      btn.disabled = true;
      try {
        var res = await fetch("/api/auth/gate/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({ password: pw })
        });
        if (res.ok) { window.location.replace("/"); return; }
        var data = await res.json().catch(function () { return {}; });
        err.textContent = (data.detail && String(data.detail)) || "Incorrect password.";
      } catch (x) {
        err.textContent = "Network error. Try again.";
      }
      btn.disabled = false;
    });
  </script>
</body>
</html>"""
