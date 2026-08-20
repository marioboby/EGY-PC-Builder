from __future__ import annotations
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from services.cache import warm_cache
from config import SCRAPERS

logger = logging.getLogger("uvicorn")

# Single scheduler instance, shared by main.py (start/stop on app lifespan)
# and routers/admin.py (read-only status endpoint).
scheduler = AsyncIOScheduler()


async def scheduled_scrape_job():
    """Wrapper so we can log outcomes and swallow errors without crashing the scheduler."""
    try:
        logger.info("Scheduled re-scrape starting...")
        await warm_cache(SCRAPERS)
        logger.info("Scheduled re-scrape complete.")
    except Exception as e:
        logger.error(f"Scheduled re-scrape failed: {e}", exc_info=True)


def start_scheduler() -> None:
    scheduler.add_job(
        scheduled_scrape_job,
        id="rescrape_job",
        trigger="interval",
        hours=6,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("APScheduler started: re-scrape every 6 hours.")


def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)
    logger.info("APScheduler stopped.")
