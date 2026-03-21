import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/")
def root():
    return {"service": "safedevops-assessment-pilot", "docs": "/docs"}
