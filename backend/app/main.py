import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import Base, engine
from app.errors import register_error_handlers
from app.middleware import RequestLoggingMiddleware
from app.routers import (
    acquisitions,
    admin,
    export,
    feedback,
    health,
    ingestion,
    manifests,
    retrieval,
    verticals,
)
from app.scheduler import configure_scheduler, scheduler

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate config
    settings.validate_on_startup()

    # Create pgvector extension and tables on startup
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    # Start scheduler
    configure_scheduler()
    if settings.scheduler_enabled:
        scheduler.start()
        logger.info("Scheduler started")

    yield

    # Shutdown
    if scheduler.running:
        scheduler.shutdown(wait=False)
    await engine.dispose()


app = FastAPI(
    title="RARIS",
    description="Regulatory Analysis & Research Intelligence System",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(manifests.router)
app.include_router(acquisitions.router)
app.include_router(ingestion.router)
app.include_router(retrieval.router)
app.include_router(verticals.router)
app.include_router(feedback.router)
app.include_router(admin.router)
app.include_router(export.router)

register_error_handlers(app)
