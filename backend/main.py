from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging

from models import BuildRequest, BuildResponse
from cache import clear_all_cache, delete_prices, warm_cache, get_cache_status, get_or_scrape
from scraper import EGPricesScraper
from builder import get_llm



# ── Scrapers ───────────────────────────────────────────────────────────────────

SCRAPERS = [
    EGPricesScraper()
]

LLM = get_llm()   # reads LLM_PROVIDER from .env

logger = logging.getLogger("uvicorn")
scheduler = AsyncIOScheduler()

# ── Startup / shutdown ─────────────────────────────────────────────────────────

async def scheduled_scrape_job():
    """Wrapper so we can log outcomes and swallow errors without crashing the scheduler."""
    try:
        logger.info("Scheduled re-scrape starting...")
        await warm_cache(SCRAPERS)  
        logger.info("Scheduled re-scrape complete.")
    except Exception as e:
        logger.error(f"Scheduled re-scrape failed: {e}", exc_info=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm the cache on startup, then hand off to the scheduler."""
    # logger.info("Starting up — warming cache...")
    # await warm_cache(SCRAPERS)

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

    yield

    scheduler.shutdown(wait=False)
    logger.info("APScheduler stopped.")
    logger.info("Shutting down.")

# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="EG PC Builder API",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten this in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Quick liveness check."""
    return {"status": "ok"}


@app.get("/admin/cache-status")
async def cache_status():
    """See what's cached and how much TTL remains on each key."""
    return await get_cache_status()

@app.get("/admin/scheduler-status")
async def scheduler_status():
    jobs = scheduler.get_jobs()
    return {
        "running": scheduler.running,
        "jobs": [
            {"id": job.id, "next_run": str(job.next_run_time)}
            for job in jobs
        ],
    }

@app.delete("/admin/clear-cache")
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

@app.post("/admin/scrape")
async def force_scrape():
    """
    Manually trigger a full re-scrape, bypassing the cache.
    Useful after a site update or if prices look stale.
    """
    await warm_cache(SCRAPERS)
    return {"status": "done"}

@app.get("/prices/{category}")
async def prices(category: str):
    """
    Return cached prices for a single category.
    Triggers a fresh scrape if the cache is cold.
    """
    from scraper import EGPricesScraper
    data = await get_or_scrape(category, SCRAPERS)
    if not data:
        raise HTTPException(status_code=404, detail=f"No products found for '{category}'")
    return {"category": category, "count": len(data), "items": data}

@app.post("/build", response_model=BuildResponse)
async def build(req: BuildRequest):
    """
    Generate a PC build recommendation based on live cached prices.
    """
    try:
        result = await LLM.generate_build(
            budget   = req.budget,
            use_case = req.use_case,
            priority = req.priority,
            notes    = req.notes,
            scrapers = SCRAPERS,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))