from __future__ import annotations

from services.scraper import EGPricesScraper

# Scrapers shared across routes, the scheduler, and admin endpoints.
# Add new sources here (e.g. a second scraper) and every consumer picks it up.
SCRAPERS = [
    EGPricesScraper(),
]
