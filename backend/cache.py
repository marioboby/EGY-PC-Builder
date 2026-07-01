# cache.py
from __future__ import annotations
import json
import redis.asyncio as redis
from scraper import BaseScraper, EGPricesScraper
import asyncio


# ── Connection ─────────────────────────────────────────────────────────────────

# Single connection pool shared across all calls
# In FastAPI this gets initialized on startup — for now localhost is fine
_pool = redis.ConnectionPool.from_url(
    "redis://localhost:6379/0",
    decode_responses=True  # return str instead of bytes
)

def get_client() -> redis.Redis:
    return redis.Redis(connection_pool=_pool)


# ── Keys ───────────────────────────────────────────────────────────────────────

def _price_key(category: str, source: str = "all") -> str:
    """
    Redis key format:  prices:{source}:{category}
    Examples:
      prices:all:gpu          ← merged from all scrapers (what /build uses)
      prices:EGPrices:gpu     ← raw from one scraper
    """
    return f"prices:{source}:{category}"


# ── TTL ────────────────────────────────────────────────────────────────────────

DEFAULT_TTL = 60 * 60 * 6  # 6 hours in seconds


# ── Core operations ────────────────────────────────────────────────────────────

async def set_prices(
    category: str,
    products: list[dict],
    source:   str = "all",
    ttl:      int = DEFAULT_TTL,
) -> None:
    """Store a product list in Redis, overwriting any existing value."""
    r   = get_client()
    key = _price_key(category, source)
    await r.set(key, json.dumps(products, ensure_ascii=False), ex=ttl)
    print(f"  [cache] SET {key} → {len(products)} products (TTL: {ttl//3600}h)")


async def get_prices(
    category: str,
    source:   str = "all",
) -> list[dict] | None:
    """
    Return cached products or None if the key doesn't exist / has expired.
    Callers should treat None as "cache miss — go scrape".
    """
    r   = get_client()
    key = _price_key(category, source)
    raw = await r.get(key)
    if raw is None:
        print(f"  [cache] MISS {key}")
        return None
    print(f"  [cache] HIT  {key}")
    return json.loads(raw)


async def delete_prices(category: str, source: str = "all") -> None:
    """Manually invalidate a cache entry — useful for forced refreshes."""
    r   = get_client()
    key = _price_key(category, source)
    await r.delete(key)
    print(f"  [cache] DEL  {key}")

async def clear_all_cache() -> None:
    """Clear all cached prices from Redis."""
    r = get_client()
    keys = await r.keys("prices:*")
    if keys:
        await r.delete(*keys)

async def get_ttl(category: str, source: str = "all") -> int:
    """Returns seconds remaining on the key, or -2 if it doesn't exist."""
    r   = get_client()
    return await r.ttl(_price_key(category, source))


# ── High-level: get or scrape ──────────────────────────────────────────────────

async def get_or_scrape(
    category: str,
    scrapers: list[BaseScraper],
    force:    bool = False,
) -> list[dict]:
    """
    Main entry point for the /build endpoint and scheduler.

    Flow:
      1. Check Redis for cached merged results
      2. If hit (and not forced) → return immediately
      3. If miss → run all scrapers for this category, merge, cache, return

    Args:
        category: e.g. "gpu", "memory"
        scrapers: list of scraper instances to pull from
        force:    if True, bypass cache and re-scrape (used by /admin/scrape)
    """
    if not force:
        cached = await get_prices(category, source="all")
        if cached is not None:
            return cached

    # Cache miss or forced — scrape fresh data
    print(f"  [cache] Scraping fresh data for '{category}'...")

    from playwright.async_api import async_playwright
    from scraper import merge_results

    all_results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for scraper in scrapers:
            if category not in scraper.CATEGORIES:
                continue
            try:
                products = await scraper.scrape_category(browser, category)
                # Also cache per-source for debugging
                await set_prices(category, products, source=scraper.SOURCE_NAME)
                all_results.append({category: products})
            except Exception as e:
                print(f"  [cache] Scraper {scraper.SOURCE_NAME} failed for '{category}': {e}")
        await browser.close()

    merged = merge_results(all_results).get(category, [])
    await set_prices(category, merged, source="all")
    return merged


# ── Bulk operations ────────────────────────────────────────────────────────────

async def warm_cache(scrapers: list[BaseScraper]) -> None:
    """
    Scrape all categories from all scrapers and populate Redis.
    Called on app startup and by the scheduler every 6 hours.
    """
    from playwright.async_api import async_playwright
    from scraper import merge_results

    print("\n── Warming cache ──")

    all_scraper_results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for scraper in scrapers:
            results = {}
            for key in scraper.CATEGORIES:
                try:
                    results[key] = await scraper.scrape_category(browser, key)
                    await set_prices(key, results[key], source=scraper.SOURCE_NAME)
                except Exception as e:
                    print(f"  [cache] {scraper.SOURCE_NAME}/{key} failed: {e}")
                    results[key] = []
            all_scraper_results.append(results)
        await browser.close()

    merged = merge_results(all_scraper_results)
    for category, products in merged.items():
        await set_prices(category, products, source="all")
        print(f"  ✓ Cached {len(products)} products → prices:all:{category}")

    print("── Cache warm complete ──\n")


async def get_cache_status() -> dict:
    """
    Returns TTL and count for every cached key.
    Useful for a /admin/cache-status endpoint later.
    """
    r       = get_client()
    keys    = await r.keys("prices:*")
    status  = {}

    for key in sorted(keys):
        ttl = await r.ttl(key)
        raw = await r.get(key)
        count = len(json.loads(raw)) if raw else 0
        status[key] = {
            "products": count,
            "ttl_seconds": ttl,
            "ttl_human": f"{ttl // 3600}h {(ttl % 3600) // 60}m" if ttl > 0 else "expired",
        }

    return status

async def main():
    # # Load your already-scraped gpu.json to test with real data
    # with open("gpu.json", encoding="utf-8") as f:
    #     gpu_products = json.load(f)

    # # 1. Store in Redis
    # await set_prices("gpu", gpu_products, source="all")

    # 2. Retrieve and verify count matches
    for category in EGPricesScraper().CATEGORIES:
        cached = await get_or_scrape(category, [EGPricesScraper()])
        print(f"Cached {category} count (all): {len(cached) if cached else 0}")
        cached_eg = await get_prices(category, source="EGPrices")
        print(f"Cached {category} count (EGPrices): {len(cached_eg) if cached_eg else 0}")


    # # 3. Check TTL is set correctly (~6 hours)
    # ttl = await get_ttl("gpu", source="all")
    # print(f"TTL: {ttl // 3600}h {(ttl % 3600) // 60}m remaining")
    # assert ttl > 0, "TTL not set!"

    # # 4. Verify cache status overview
    # status = await get_cache_status()
    # print("\nCache status:")
    # for key, info in status.items():
    #     print(f"  {key}: {info['products']} products, expires in {info['ttl_human']}")

    # print("\n✓ All checks passed")


if __name__ == "__main__":
    asyncio.run(main())