# builder.py
from __future__ import annotations
import json
import anthropic
from cache import get_or_scrape
from scraper import BaseScraper

client = anthropic.AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env

CATEGORIES = ["gpu", "processor", "motherboard", "memory", "storage", "psu", "case", "cooler"]

# How many products per category to send Claude
# Enough for good coverage, small enough to stay within context
PRODUCTS_PER_CATEGORY = 20


async def build_price_block(scrapers: list[BaseScraper]) -> str:
    """
    Pull live prices from cache for all categories and format them
    into a structured block to inject into Claude's system prompt.
    """
    sections = []

    for category in CATEGORIES:
        products = await get_or_scrape(category, scrapers)
        if not products:
            continue

        # Sort by price so Claude sees cheapest options first
        products = sorted(products, key=lambda p: p["price_egp"])
        top = products[:PRODUCTS_PER_CATEGORY]

        lines = [
            f"  - {p['name']}: {p['price_egp']:,} EGP (at {p['store']})"
            for p in top
        ]
        sections.append(f"{category.upper()}:\n" + "\n".join(lines))

    return "\n\n".join(sections)


async def generate_build(
    budget:   int,
    use_case: str,
    priority: str,
    notes:    str,
    scrapers: list[BaseScraper],
) -> dict:
    price_block = await build_price_block(scrapers)

    system_prompt = f"""You are an expert PC builder specializing in the Egyptian market.

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

    user_msg = (
        f"Budget: {budget:,} EGP\n"
        f"Use case: {use_case}\n"
        f"Priority: {priority}\n"
        f"Notes: {notes or 'none'}"
    )

    response = await client.messages.create(
        model      = "claude-sonnet-4-5",
        max_tokens = 4096,
        system     = system_prompt,
        messages   = [{"role": "user", "content": user_msg}],
    )

    text = response.content[0].text
    first, last = text.index("{"), text.rindex("}")
    return json.loads(text[first : last + 1])