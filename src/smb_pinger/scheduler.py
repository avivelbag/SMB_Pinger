import logging
from collections.abc import Callable, Coroutine
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)


def create_scheduler(
    job_func: Callable[[], Coroutine[Any, Any, None]],
    interval_minutes: int = 15,
) -> AsyncIOScheduler:
    """Create an APScheduler AsyncIOScheduler with a single interval job.

    The job runs immediately on start, then repeats every `interval_minutes`.
    max_instances=1 prevents overlapping runs.
    """
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        job_func,
        "interval",
        minutes=interval_minutes,
        max_instances=1,
        id="check_cycle",
        name="Website check cycle",
    )
    logger.info("Scheduler configured: every %d minutes", interval_minutes)
    return scheduler
