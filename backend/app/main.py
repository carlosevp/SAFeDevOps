import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routers.assessment_routes import router as assessment_router
from app.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    (settings.upload_dir.parent / "exports").mkdir(parents=True, exist_ok=True)
    init_db()
    logger.info("Database initialized; data_dir=%s", settings.data_dir)
    yield


app = FastAPI(title="SAFe DevOps Self-Assessment Pilot", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(assessment_router)

_SPA_DIR = Path(__file__).resolve().parent.parent / "spa_dist"
_SPA_ASSETS = _SPA_DIR / "assets"


def _spa_enabled() -> bool:
    return (_SPA_DIR / "index.html").is_file()


if _SPA_ASSETS.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_SPA_ASSETS)), name="spa_assets")

# Vite copies `public/` files next to index.html (e.g. logo-placeholder.svg)
if _spa_enabled():
    for entry in _SPA_DIR.iterdir():
        if not entry.is_file() or entry.name == "index.html":
            continue
        fp = entry.resolve()

        def _make_file_response(path: Path):
            def _send() -> FileResponse:
                return FileResponse(path)

            return _send

        app.add_api_route(f"/{entry.name}", _make_file_response(fp), methods=["GET"])


@app.get("/")
def root():
    if _spa_enabled():
        return FileResponse(_SPA_DIR / "index.html")
    return {"service": "safedevops-assessment-pilot", "docs": "/docs"}
