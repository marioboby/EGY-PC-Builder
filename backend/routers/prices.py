from __future__ import annotations
from fastapi import APIRouter, HTTPException

from core.config import SCRAPERS
from services.cache import get_or_scrape

router = APIRouter(tags=["prices"])


@router.get("/prices/{category}")
async def prices(category: str):
    """
    Return cached prices for a single category.
    Triggers a fresh scrape if the cache is cold.
    """
    data = await get_or_scrape(category, SCRAPERS)
    if not data:
        raise HTTPException(status_code=404, detail=f"No products found for '{category}'")
    return {"category": category, "count": len(data), "items": data}
