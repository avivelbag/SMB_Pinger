import logging
import logging.config
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2_fragments.fastapi import Jinja2Blocks

from smb_pinger.check_cycle import check_all_sites
from smb_pinger.config import Settings
from smb_pinger.database import get_db, init_db
from smb_pinger.routes.admin import create_admin_router
from smb_pinger.routes.dashboard import router as dashboard_router
from smb_pinger.scheduler import create_scheduler
from smb_pinger.security import SecurityHeadersMiddleware

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
}

logger = logging.getLogger(__name__)

# Resolve paths relative to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown."""
    logging.config.dictConfig(LOGGING_CONFIG)

    settings: Settings = app.state.settings

    # Initialize database
    await init_db(settings.db_path)
    logger.info("Database ready at %s", settings.db_path)

    # Create shared httpx client
    client = httpx.AsyncClient(
        headers={"User-Agent": settings.user_agent},
        follow_redirects=True,
        timeout=httpx.Timeout(settings.timeout_seconds),
    )
    app.state.http_client = client

    # Define the check cycle job
    async def run_check_cycle() -> None:
        async with get_db(settings.db_path) as db:
            await check_all_sites(
                db,
                client,
                concurrency=settings.concurrency_limit,
                request_timeout=settings.timeout_seconds,
                max_redirects=settings.max_redirects,
            )

    # Start scheduler
    scheduler = create_scheduler(
        run_check_cycle,
        interval_minutes=settings.check_interval_minutes,
    )
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info("Application started")

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    await client.aclose()
    logger.info("Application shut down")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = Settings()

    app = FastAPI(title="SMB Pinger", lifespan=lifespan)
    app.state.settings = settings

    # Templates
    templates = Jinja2Blocks(directory=str(TEMPLATES_DIR))
    app.state.templates = templates

    # Static files
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Security middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Routes
    app.include_router(dashboard_router)
    app.include_router(create_admin_router(settings.admin_password_hash))

    @app.get("/health")
    async def health() -> JSONResponse:
        """Health check endpoint. Returns 503 if last check cycle is stale."""
        try:
            async with get_db(settings.db_path) as db:
                cursor = await db.execute(
                    "SELECT MAX(checked_at) as last_check FROM ping_results"
                )
                row = await cursor.fetchone()

            if row and row["last_check"]:
                last_check = datetime.fromisoformat(
                    row["last_check"]
                ).replace(tzinfo=UTC)
                stale_threshold = datetime.now(UTC) - timedelta(minutes=30)
                if last_check < stale_threshold:
                    return JSONResponse(
                        {"status": "degraded"},
                        status_code=503,
                    )
            return JSONResponse({"status": "ok"})
        except Exception:
            logger.exception("Health check failed")
            return JSONResponse({"status": "degraded"}, status_code=503)

    return app


app = create_app()
