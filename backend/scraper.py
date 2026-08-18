from __future__ import annotations
from abc import ABC, abstractmethod
from playwright.async_api import async_playwright, Browser
from bs4 import BeautifulSoup
import asyncio
import json

# ── Base class ─────────────────────────────────────────────────────────────────

class BaseScraper(ABC):
    """
    Abstract base for all scrapers.
    Subclasses define their own categories, selectors, and parsing logic.
    Each scraper manages its own browser lifecycle.
    """

    SOURCE_NAME: str = ""
    CATEGORIES:  dict[str, str] = {}

    async def scrape_all(self) -> dict[str, list[dict]]:
        """Scrape all categories and return {category: [products]}."""
        results = {}
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            for key in self.CATEGORIES:
                try:
                    results[key] = await self.scrape_category(browser, key)
                except Exception as e:
                    print(f"  ✗ [{self.SOURCE_NAME}] Failed to scrape '{key}': {e}")
                    results[key] = []
            await browser.close()
        return results

    async def scrape_category(self, browser: Browser, category_key: str) -> list[dict]:
        """Scrape all pages of one category and return deduplicated products."""
        print(f"\n── [{self.SOURCE_NAME}] Scraping: {category_key} ──")
        url = self.CATEGORIES[category_key]

        pages_html = await self._get_all_pages_html(browser, url)

        products = []
        for html in pages_html:
            products.extend(self._parse_cards(html))

        unique = self._deduplicate(products)
        print(f"  ✓ {category_key}: {len(unique)} unique products across {len(pages_html)} pages")
        return unique

    # ── Must implement ─────────────────────────────────────────────────────────

    @abstractmethod
    def _card_selector(self) -> str:
        """CSS selector that matches a single product card."""
        ...

    @abstractmethod
    def _next_btn_selector(self) -> str:
        """CSS selector for the Next page button/link."""
        ...

    @abstractmethod
    def _parse_cards(self, html: str) -> list[dict]:
        """
        Parse raw HTML and return a list of product dicts.
        Each dict must have at minimum: name, price_egp, store, source.
        """
        ...

    # ── Pagination — override if the site uses a different pattern ─────────────

    async def _get_all_pages_html(self, browser: Browser, base_url: str) -> list[str]:
        """
        Default pagination: click Next button, stop when it disappears
        or points to a page <= current (wrap-around guard).
        Overriding this method for sites with infinite scroll or different patterns.
        """
        page = await browser.new_page()
        await page.goto(base_url, wait_until="networkidle")
        await page.wait_for_selector(self._card_selector(), timeout=15000)

        pages_html = []
        page_num = 1

        while True:
            print(f"  Fetching page {page_num}...")
            pages_html.append(await page.content())

            next_btn = page.locator(self._next_btn_selector()).last

            if await next_btn.count() == 0:
                print(f"  No Next button — stopped at page {page_num}.")
                break

            href = await next_btn.get_attribute("href")
            if not href or "page=" not in href:
                print(f"  Next button has no valid href — stopped at page {page_num}.")
                break

            next_page_num = int(href.split("page=")[-1])
            if next_page_num <= page_num:
                print(f"  Next button wraps to page {next_page_num} — last page was {page_num}.")
                break

            await next_btn.click()
            await page.wait_for_selector(
                f"nav div:text-is('{next_page_num}')", timeout=15000
            )
            await page.wait_for_selector(self._card_selector(), timeout=15000)
            page_num += 1

        await page.close()
        return pages_html

    # ── Shared utilities ───────────────────────────────────────────────────────

    def _deduplicate(self, products: list[dict]) -> list[dict]:
        """Remove duplicates by (name, store) pair."""
        seen = set()
        unique = []
        for p in products:
            key = (p["name"], p["store"])
            if key not in seen:
                seen.add(key)
                unique.append(p)
        return unique


# ── EGPrices implementation ────────────────────────────────────────────────────

class EGPricesScraper(BaseScraper):

    SOURCE_NAME = "EGPrices"

    CATEGORIES = {
        "gpu":         "https://www.egprices.com/en/category/computers/computer-components-hardware/graphics-cards",
        "memory":      "https://www.egprices.com/en/category/computers/components/memory",
        "motherboard": "https://www.egprices.com/en/category/computers/computer-components-hardware/motherboards",
        "processor":   "https://www.egprices.com/en/category/computers/components/processors",
        "case":        "https://www.egprices.com/en/category/computers/components/cases",
        "psu":         "https://www.egprices.com/en/category/computers/components/power-supplies",
        "storage":     "https://www.egprices.com/en/category/computers/storage",
        "cooler":      "https://www.egprices.com/en/category/computers/computer-components-hardware/fans-cooling-systems",
    }

    def _card_selector(self) -> str:
        return "ul > li.group.relative.rounded"

    def _next_btn_selector(self) -> str:
        return "a:has(svg.lucide-chevron-right)"

    def _parse_cards(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        products = []

        for card in soup.select(self._card_selector()):
            name_el  = card.select_one("h3 a")
            price_el = card.select_one("span.text-rose-700 span")
            store_el = card.select_one("div.flex.flex-row img")

            name  = name_el.get_text(strip=True) if name_el else None
            store = store_el.get("alt")          if store_el else "N/A"
            price = None

            if price_el:
                raw = price_el.get_text(strip=True).replace(",", "")
                print(f"  Found product: name={name} price={raw} store={store}")
                price = int(raw) if raw.isdigit() else None

            if name and price:
                products.append({
                    "name":      name,
                    "price_egp": price,
                    "store":     store,
                    "source":    self.SOURCE_NAME,
                })
            else:
                print(f"  ✗ Skipped — name={name} price={price} store={store}")

        return products


# ── Merge results from multiple scrapers ───────────────────────────────────────

def merge_results(
    all_results: list[dict[str, list[dict]]] # List of {category: [products]} dicts from each scraper
) -> dict[str, list[dict]]:
    """
    Combine results from multiple scrapers into one dict.
    Same category from different sources gets merged into one list.
    Deduplication is by (name, store) across all sources.
    """
    merged: dict[str, list[dict]] = {}
    seen:   dict[str, set]        = {}

    for results in all_results:
        for category, products in results.items():
            if category not in merged:
                merged[category] = []
                seen[category]   = set()
            for p in products:
                key = (p["name"], p["store"])
                if key not in seen[category]:
                    seen[category].add(key)
                    merged[category].append(p)

    return merged


# ── Entry point ────────────────────────────────────────────────────────────────

def save_results(results: dict[str, list[dict]]) -> None:
    """Overwrite JSON files with fresh data."""
    for category, products in results.items():
        filename = f"{category}.json"

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(products)} products → {filename}")


async def main():
    scrapers = [
        EGPricesScraper()
    ]

    all_results = await asyncio.gather(*[s.scrape_all() for s in scrapers])
    merged = merge_results(list(all_results))
    save_results(merged)


if __name__ == "__main__":
    asyncio.run(main())