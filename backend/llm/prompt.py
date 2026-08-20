from __future__ import annotations
import json

from services.cache import get_or_scrape
from services.scraper import BaseScraper

CATEGORIES = ["gpu", "processor", "motherboard", "memory", "storage", "psu", "case", "cooler"]
PRODUCTS_PER_CATEGORY = 20


# ── Shared: build the price block ─────────────────────────────────────────────

async def build_price_block(scrapers: list[BaseScraper]) -> str:
    sections = []
    for category in CATEGORIES:
        products = await get_or_scrape(category, scrapers)
        if not products:
            continue
        products = sorted(products, key=lambda p: p["price_egp"])
        top = products[:PRODUCTS_PER_CATEGORY]
        lines = [
            f"  - {p['name']}: {p['price_egp']:,} EGP (at {p['store']})"
            for p in top
        ]
        sections.append(f"{category.upper()}:\n" + "\n".join(lines))
    return "\n\n".join(sections)


def build_system_prompt(price_block: str) -> str:
    return f"""You are an expert PC builder specializing in the Egyptian market.

LIVE PRICES scraped from EGPrices.com (updated every 6 hours):

{price_block}

RULES:
- Only recommend components from the list above — never invent products or prices
- Include the store name from the data in each part's notes
- A build must include: CPU, Motherboard, RAM, GPU (unless office build), Storage, PSU, Case
- Add a Cooler only if the CPU doesn't include a box cooler
- Ensure CPU and motherboard socket compatibility (e.g. LGA1700 for 13th gen Intel)
- Ensure RAM type matches motherboard (DDR4 vs DDR5)
- Total must not exceed the budget — if impossible, set feasibility to "infeasible"
- Return ONLY a valid JSON object, no markdown, no explanation outside the JSON

JSON structure:
{{
  "summary": "1-2 sentence overview",
  "feasibility": "feasible" | "tight" | "infeasible",
  "feasibility_note": "explanation",
  "total_estimated": <number>,
  "parts": [
    {{
      "category": "CPU" | "Motherboard" | "RAM" | "GPU" | "Storage" | "PSU" | "Case" | "Cooler",
      "name": "exact product name from the list",
      "price_egp": <number>,
      "store": "store name from the list",
      "notes": "why this was chosen + compatibility notes",
      "egprices_search": "short search term for egprices.com"
    }}
  ],
  "alternatives": [
    {{"part": "category", "alternative": "product name", "reason": "why swap"}}
  ],
  "tips": ["tip1", "tip2", "tip3"],
  "upgrade_path": "what to upgrade first when budget allows"
}}"""


def build_user_message(budget: int, use_case: str, priority: str, notes: str) -> str:
    return (
        f"Budget: {budget:,} EGP\n"
        f"Use case: {use_case}\n"
        f"Priority: {priority}\n"
        f"Notes: {notes or 'none'}"
    )


def parse_response(text: str) -> dict:
    """Extract JSON from model response regardless of surrounding text."""
    first, last = text.index("{"), text.rindex("}")
    return json.loads(text[first:last + 1])
