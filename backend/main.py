# main.py
from __future__ import annotations

import sys
import asyncio

if sys.platform == 'win32':
    # Change 'Selector' to 'Proactor' to allow Playwright subprocesses
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import BuildRequest, BuildResponse
from cache import warm_cache, get_cache_status, get_or_scrape
from scraper import EGPricesScraper


# ── Scrapers ───────────────────────────────────────────────────────────────────

SCRAPERS = [
    EGPricesScraper()
]

# ── Startup / shutdown ─────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm the cache on startup, then hand off to the scheduler."""
    print("Starting up — warming cache...")
    await warm_cache(SCRAPERS)
    # scheduler starts here in the next step
    yield
    print("Shutting down.")

# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="EG PC Builder API",
    version="0.1.0",
    lifespan=lifespan,
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
    from builder import generate_build
    try:
        result = await generate_build(
            budget   = req.budget,
            use_case = req.use_case,
            priority = req.priority,
            notes    = req.notes,
            scrapers = SCRAPERS,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))