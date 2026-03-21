"""Register optional Vite `dist` files on the FastAPI app (production Docker image)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse


def register_spa_public_files(application: FastAPI, spa_dir: Path) -> None:
    """Serve root-level files from the Vite build (e.g. public/logo-placeholder.svg)."""
    if not (spa_dir / "index.html").is_file():
        return
    for entry in spa_dir.iterdir():
        if not entry.is_file() or entry.name == "index.html":
            continue
        resolved = entry.resolve()

        def make_handler(fp: Path) -> object:
            def _send() -> FileResponse:
                return FileResponse(fp)

            return _send

        application.add_api_route(f"/{entry.name}", make_handler(resolved), methods=["GET"])
