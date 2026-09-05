"""Protecting a local engine from the browser the user is also using.

`pravrudhi app` runs an unauthenticated API on localhost that can start GPU work. That combination is the classic
setup for cross-site request forgery: any page a user visits while the engine is running can issue requests to
127.0.0.1, and if the engine answers them the page can start runs, stop runs, or read the user's results. Being
bound to loopback prevents nothing here, because the attacker's code runs inside the user's own browser.

Three defences, each covering what the others do not.

Cross-origin requests are refused by default. The API sends no permissive CORS headers unless the operator names
the origins, so a malicious page cannot read a response even when it can send a request.

The Host header must name a loopback address. Refusing anything else defeats DNS rebinding, where an attacker's
domain resolves to 127.0.0.1 so that the browser believes the request is same-origin.

State-changing requests carry a token. The token is generated on first use, stored readable only by the user, and
served only to a same-origin caller, so a page that can still reach the engine cannot start a run without it. Read
endpoints stay open, because a local dashboard should work without ceremony and reading is not the risk.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

LOCAL_HOSTS = ("127.0.0.1", "localhost", "[::1]", "::1")
TOKEN_HEADER = "x-pravrudhi-token"


def token_path(root: Path) -> Path:
    return Path(root) / ".pravrudhi" / "app_token"


def app_token(root: Path) -> str:
    """The engine's local token, created on first use with owner-only permissions."""
    p = token_path(root)
    if p.exists():
        text = p.read_text().strip()
        if text:
            return text
    p.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    p.write_text(token + "\n")
    os.chmod(p, 0o600)
    return token


def _host_is_local(host_header: str) -> bool:
    host = host_header.split(":")[0].strip().lower() if host_header else ""
    if host_header.startswith("["):  # bracketed IPv6, e.g. [::1]:8008
        host = host_header.split("]")[0] + "]"
    return host in LOCAL_HOSTS or host == ""


def allowed_origins() -> list[str]:
    """Origins the operator has explicitly allowed. Empty by default: no cross-origin access at all."""
    raw = os.environ.get("PRAVRUDHI_ALLOWED_ORIGINS", "")
    return [o.strip() for o in raw.split(",") if o.strip()]


class LocalGuard(BaseHTTPMiddleware):
    """Reject non-loopback Host headers, and require the local token for state-changing methods."""

    def __init__(self, app: FastAPI, root: Path, *, enforce: bool = True) -> None:
        super().__init__(app)
        self.root = Path(root)
        self.enforce = enforce

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        if not self.enforce:
            return await call_next(request)
        host = request.headers.get("host", "")
        origin = request.headers.get("origin", "")
        permitted = allowed_origins()
        if not _host_is_local(host) and host not in permitted and not any(o.endswith(host) for o in permitted):
            return JSONResponse(
                {"detail": "refused: the Host header is not a loopback address (DNS-rebinding guard)"}, status_code=421
            )
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if origin and origin not in permitted:
                return JSONResponse({"detail": "refused: cross-origin state change"}, status_code=403)
            supplied = request.headers.get(TOKEN_HEADER, "")
            if not secrets.compare_digest(supplied, app_token(self.root)):
                return JSONResponse(
                    {"detail": f"refused: send the engine's local token in {TOKEN_HEADER} (see .pravrudhi/app_token)"},
                    status_code=401,
                )
        return await call_next(request)


def install(app: FastAPI, root: Path, *, enforce: bool = True) -> None:
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins(),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["content-type", TOKEN_HEADER, "x-pravrudhi-operator"],
    )
    app.add_middleware(LocalGuard, root=root, enforce=enforce)  # type: ignore[arg-type]

    @app.get("/app-token")
    def token(request: Request) -> Response:
        """The local token, for the interface this engine serves. Same-origin callers only."""
        origin = request.headers.get("origin", "")
        if origin and origin not in allowed_origins():
            raise HTTPException(status_code=403, detail="cross-origin callers cannot read the local token")
        return JSONResponse({"token": app_token(root)})
