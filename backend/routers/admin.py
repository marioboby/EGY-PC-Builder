from __future__ import annotations
from fastapi import APIRouter

from core.config import SCRAPERS
from services.cache import clear_all_cache, delete_prices, warm_cache, get_cache_status
from core.scheduler import scheduler

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/cache-status")
async def cache_status():
    """See what's cached and how much TTL remains on each key."""
    return await get_cache_status()


@router.get("/scheduler-status")
async def scheduler_status():
    jobs = scheduler.get_jobs()
    return {
        "running": scheduler.running,
        "jobs": [
            {"id": job.id, "next_run": str(job.next_run_time)}
            for job in jobs
        ],
    }


@router.delete("/clear-cache")
async def clear_cache(category: str | None = None):
    """
    Clear cached prices from Redis.
    If a category is provided, clear only that category's cache.
    Otherwise, clear all caches.
    Useful for testing or if the cache is corrupted.
    """
    if category:
        await delete_prices(category, source="all")
        return {"status": "done", "cleared_category": category}
    await clear_all_cache()
    return {"status": "done"}


@router.post("/scrape")
async def force_scrape():
    """
    Manually trigger a full re-scrape, bypassing the cache.
    Useful after a site update or if prices look stale.
    """
    await warm_cache(SCRAPERS)
    return {"status": "done"}
