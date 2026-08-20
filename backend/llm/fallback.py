from __future__ import annotations
import time
import logging
import asyncio

from services.scraper import BaseScraper
from .base import BaseLLM
from .prompt import build_price_block, build_system_prompt, build_user_message, parse_response

logger = logging.getLogger("uvicorn")


async def generate_build_with_fallback(
    providers: list[BaseLLM],
    budget:    int,
    use_case:  str,
    priority:  str,
    notes:     str,
    scrapers:  list[BaseScraper],
    timeout:   int = 45,
) -> dict:
    """
    Builds the price block ONCE, then tries each provider in order until
    one succeeds. A slow/down/malformed-response provider just moves to
    the next one instead of failing the whole request.
    """
    price_block = await build_price_block(scrapers)
    system      = build_system_prompt(price_block)
    user_msg    = build_user_message(budget, use_case, priority, notes)

    last_err = None
    for provider in providers:
        name = provider.__class__.__name__
        t0 = time.perf_counter()
        try:
            text = await asyncio.wait_for(
                provider._complete(system, user_msg), timeout=timeout
            )
            result = parse_response(text)  # json.JSONDecodeError also falls through to except below
            logger.info(f"[fallback] {name} succeeded in {time.perf_counter() - t0:.2f}s")
            return result
        except asyncio.TimeoutError:
            logger.warning(f"[fallback] {name} timed out after {timeout}s")
            last_err = TimeoutError(f"{name} timed out after {timeout}s")
        except Exception as e:
            logger.warning(f"[fallback] {name} failed: {e}")
            last_err = e
        continue

    raise last_err
