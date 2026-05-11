# scraper.py
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import asyncio
import json


CATEGORIES = {
    "gpu":  "https://www.egprices.com/en/category/computers/computer-components-hardware/graphics-cards", 
    "motherboard": "https://www.egprices.com/en/category/computers/computer-components-hardware/motherboards",
    "memory": "https://www.egprices.com/en/category/computers/components/memory"
}    

async def scrape_category(category_key: str) -> list[dict]:
    url = CATEGORIES[category_key]

    async with async_playwright() as p:
          
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        await page.goto(url, wait_until='networkidle')
        card_selector = "ul > li.group.relative.rounded"
          
        # Wait for product cards to load
        await page.wait_for_selector(card_selector, timeout=15000)
        count = await page.locator(card_selector).count()
        print(f"Found {count} product cards.")
        html = await page.content()
        await browser.close()
      
    soup = BeautifulSoup(html, 'html.parser')
    products = []

    for card in soup.select(card_selector):
        # --- NAME ---
        # It's in the <a> inside <h3>, grab the text and strip whitespace
        name_el = card.select_one("h3 a")
        name = name_el.get_text(strip=True) if name_el else None

        # --- PRICE ---
        # The price number is in <span class="text-xl font-medium text-rose-700">
        # then inside that is another <span> with just the number e.g. "210,000"
        price_el = card.select_one("span.text-rose-700 span")
        price = None
        if price_el:
            raw = price_el.get_text(strip=True).replace(",", "")
            price = int(raw) if raw.isdigit() else None

        # --- STORE ---
        # The store logo <img> has alt="Store Name" — that's the cleanest source
        store_el = card.select_one("div.flex.flex-row img")
        store = store_el.get("alt") if store_el else "N/A"

        if name and price:
            products.append({
                "name":      name,
                "price_egp": price,
                "store":     store,
            })
            print(f"  ✓ {name} | {price:,} EGP | {store}")
        else:
            print(f"  ✗ Skipped card — name={name} price={price}")

    return products

async def main():
    gpus, motherboards, memory = await asyncio.gather(
        scrape_category("gpu"),
        scrape_category("motherboard"),
        scrape_category("memory")
    )

    # save to JSON files
    with open("gpus.json", "w", encoding="utf-8") as f:
        json.dump(gpus, f, ensure_ascii=False, indent=2)

    with open("motherboards.json", "w", encoding="utf-8") as f:
        json.dump(motherboards, f, ensure_ascii=False, indent=2)

    with open("memory.json", "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

asyncio.run(main())