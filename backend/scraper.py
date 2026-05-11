from playwright.async_api import async_playwright, Browser
from bs4 import BeautifulSoup
import asyncio
import json

CATEGORIES = {
    "gpu":         "https://www.egprices.com/en/category/computers/computer-components-hardware/graphics-cards",
    "memory":      "https://www.egprices.com/en/category/computers/components/memory",
    "motherboard": "https://www.egprices.com/en/category/computers/computer-components-hardware/motherboards",
    "processor":   "https://www.egprices.com/en/category/computers/components/processors",
    "case": "https://www.egprices.com/en/category/computers/components/cases",
    "psu":  "https://www.egprices.com/en/category/computers/components/power-supplies"
}

CARD_SELECTOR = "ul > li.group.relative.rounded"

NEXT_BTN_SELECTOR = "a:has(svg.lucide-chevron-right)"


# ── Browser ────────────────────────────────────────────────────────────────────

async def get_page_html(browser: Browser, url: str) -> str:
    """Navigate to a URL and return fully-rendered HTML."""
    page = await browser.new_page()
    await page.goto(url, wait_until="networkidle")
    await page.wait_for_selector(CARD_SELECTOR, timeout=15000)
    html = await page.content()
    await page.close()
    return html


# ── Parsing ────────────────────────────────────────────────────────────────────

def parse_cards(html: str) -> list[dict]:
    """Extract product name, price, and store from rendered HTML."""
    soup = BeautifulSoup(html, "html.parser")
    products = []

    for card in soup.select(CARD_SELECTOR):
        name_el  = card.select_one("h3 a")
        price_el = card.select_one("span.text-rose-700 span")
        store_el = card.select_one("div.flex.flex-row img")

        name  = name_el.get_text(strip=True) if name_el else None
        store = store_el.get("alt")          if store_el else "N/A"
        price = None

        if price_el:
            raw = price_el.get_text(strip=True).replace(",", "")
            price = int(raw) if raw.isdigit() else None

        if name and price:
            products.append({"name": name, "price_egp": price, "store": store})
        else:
            print(f"  ✗ Skipped — name={name} price={price}")

    return products

# ── Pagination ─────────────────────────────────────────────────────────────────

NEXT_BTN_SELECTOR = "a:has(svg.lucide-chevron-right)"

async def get_all_pages_html(browser: Browser, base_url: str) -> list[str]:
    """Walk pages by clicking the Next button — stops when it disappears."""
    page = await browser.new_page()
    await page.goto(base_url, wait_until="networkidle")
    await page.wait_for_selector(CARD_SELECTOR, timeout=15000)

    pages_html = []
    page_num = 1

    while True:
        print(f"  Scraping page {page_num}...")
        pages_html.append(await page.content())

        next_btn = page.locator(NEXT_BTN_SELECTOR).last

        if await next_btn.count() == 0:
            print(f"  No Next button — stopped at page {page_num}.")
            break

        print(next_btn)
        # Get the href and extract the target page number
        href = await next_btn.get_attribute("href")
        next_page_num = int(href.split("page=")[-1])

        # If next button points to a page <= current, it wrapped — stop
        if next_page_num <= page_num:
            print(f"  Next button wraps to page {next_page_num} — last page was {page_num}.")
            break

        await next_btn.click()
        await page.wait_for_selector(f"nav div:text-is('{next_page_num}')", timeout=15000)
        await page.wait_for_selector(CARD_SELECTOR, timeout=15000)
        page_num += 1

    await page.close()
    return pages_html


# ── Category scraper ───────────────────────────────────────────────────────────

async def scrape_category(browser: Browser, category_key: str) -> list[dict]:
    """Scrape all pages of a single category and return deduplicated products."""
    print(f"\n── Scraping: {category_key} ──")
    url = CATEGORIES[category_key]

    pages_html = await get_all_pages_html(browser, url)

    products = []
    for html in pages_html:
        products.extend(parse_cards(html))

    # Deduplicate by (name, store) — same product can appear on multiple pages
    seen = set()
    unique = []
    for p in products:
        key = (p["name"], p["store"])
        if key not in seen:
            seen.add(key)
            unique.append(p)
        

    print(f"  ✓ {category_key}: {len(unique)} unique products across {len(pages_html)} pages")
    return unique


# ── Entry point ────────────────────────────────────────────────────────────────

async def scrape_all_categories() -> dict[str, list[dict]]:
    """
    Scrape all categories sharing one browser instance.
    Categories run sequentially to avoid hammering the site.
    """
    results = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)

        for key in CATEGORIES:
            results[key] = await scrape_category(browser, key)

        await browser.close()

    return results


def save_results(results: dict[str, list[dict]]) -> None:
    """Overwrite JSON files with fresh data — no appending to avoid duplicates."""
    for category, products in results.items():
        filename = f"{category}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(products)} products → {filename}")


async def main():
    results = await scrape_all_categories()
    save_results(results)


asyncio.run(main())