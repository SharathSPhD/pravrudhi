"""`pravrudhi app`: the product, served locally by the engine.

One process, one port. The engine's API and the built web app are served together, so a user runs a single command
and opens a browser; there is no account, no cloud and no second service to start. The same frontend build is what
the hosted site deploys, pointed at a demo backend instead of this one, so the local app and the public app cannot
drift apart.

Route order matters: the API is registered first, the static frontend is mounted last as a catch-all, and any
client-side route (a browser refresh on /runs) falls back to index.html the way a static export expects.
"""

from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from pravrudhi.api.runs import build_router
from pravrudhi.api.server import create_app

DEFAULT_PORT = 8008


def frontend_dir(root: Path) -> Path | None:
    """The static export, if it has been built. Absent means API-only, which is still a working engine."""
    out = Path(root) / "app" / "frontend" / "out"
    return out if (out / "index.html").exists() else None


class _SpaStatic(StaticFiles):
    """Static files with an index.html fallback for client-side routes."""

    async def get_response(self, path: str, scope: Any) -> Any:
        try:
            return await super().get_response(path, scope)
        except Exception:
            index = Path(self.directory) / "index.html"  # type: ignore[arg-type]
            if index.exists():
                return FileResponse(index)
            raise


def build_app(root: Path) -> FastAPI:
    root = Path(root)
    app = create_app(root)
    app.include_router(build_router(root))
    fe = frontend_dir(root)
    if fe is not None:
        app.mount("/", _SpaStatic(directory=str(fe), html=True), name="frontend")
    return app


def serve(root: Path, *, host: str = "127.0.0.1", port: int = DEFAULT_PORT, open_browser: bool = True) -> None:
    import uvicorn

    app = build_app(root)
    if open_browser:
        webbrowser.open(f"http://{host}:{port}/")
    uvicorn.run(app, host=host, port=port, log_level="info")
