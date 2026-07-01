# builder.py
from __future__ import annotations
from abc import ABC, abstractmethod
import json
import os

from google import genai
from google.genai import types
from cache import get_or_scrape
from scraper import BaseScraper

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


# ── Base LLM class ─────────────────────────────────────────────────────────────

class BaseLLM(ABC):
    """
    Abstract base for all LLM providers.
    Subclasses implement only _complete() — everything else is shared.
    """

    MODEL_NAME: str = ""

    async def generate_build(
        self,
        budget:   int,
        use_case: str,
        priority: str,
        notes:    str,
        scrapers: list[BaseScraper],
    ) -> dict:
        price_block = await build_price_block(scrapers)
        system      = build_system_prompt(price_block)
        user_msg    = build_user_message(budget, use_case, priority, notes)
        text        = await self._complete(system, user_msg)
        return parse_response(text)

    @abstractmethod
    async def _complete(self, system: str, user_msg: str) -> str:
        """
        Send system + user message to the model, return raw text response.
        Each provider implements this differently.
        """
        ...


# ── Claude (Anthropic) ─────────────────────────────────────────────────────────

class ClaudeLLM(BaseLLM):
    MODEL_NAME = "claude-sonnet-4-5"

    def __init__(self, model: str = MODEL_NAME):
        import anthropic
        self.model  = model
        self.client = anthropic.AsyncAnthropic()  # reads ANTHROPIC_API_KEY

    async def _complete(self, system: str, user_msg: str) -> str:
        response = await self.client.messages.create(
            model    = self.model,
            max_tokens = 4096,
            system   = system,
            messages = [{"role": "user", "content": user_msg}],
        )
        return response.content[0].text


# ── GPT (OpenAI) ───────────────────────────────────────────────────────────────

class GPT(BaseLLM):
    MODEL_NAME = "gpt-4o"

    def __init__(self, model: str = MODEL_NAME):
        from openai import AsyncOpenAI
        self.model  = model
        self.client = AsyncOpenAI()  # reads OPENAI_API_KEY

    async def _complete(self, system: str, user_msg: str) -> str:
        response = await self.client.chat.completions.create(
            model    = self.model,
            max_tokens = 4096,
            messages = [
                {"role": "system",  "content": system},
                {"role": "user",    "content": user_msg},
            ],
        )
        return response.choices[0].message.content


# ── Gemini (Google) ────────────────────────────────────────────────────────────

class GeminiLLM(BaseLLM):
    MODEL_NAME = "gemini-3.5-flash"

    def __init__(self, model: str = MODEL_NAME):
        self.model_name = model
        
        # 1. The new SDK relies on a Client instance rather than a global genai.configure()
        # Note: genai.Client() automatically looks for the GEMINI_API_KEY environment 
        # variable, but passing it explicitly here works perfectly too.
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    async def _complete(self, system: str, user_msg: str) -> str:
        # 2. Native async support is accessed via `self.client.aio`
        # 3. System instructions are now passed via types.GenerateContentConfig
        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=user_msg,
            config=types.GenerateContentConfig(
                system_instruction=system
            )
        )
        
        return response.text


# ── Local model via Ollama ─────────────────────────────────────────────────────

class OllamaLLM(BaseLLM):
    """
    Runs any local model through Ollama (ollama.com).
    Install Ollama, then: ollama pull llama3 / mistral / deepseek-r1 / etc.
    """
    MODEL_NAME = "llama3"

    def __init__(self, model: str = MODEL_NAME, base_url: str = "http://localhost:11434"):
        from openai import AsyncOpenAI
        self.model  = model
        # Ollama exposes an OpenAI-compatible API — no extra SDK needed
        self.client = AsyncOpenAI(
            api_key  = "ollama",   # required but ignored by Ollama
            base_url = f"{base_url}/v1",
        )

    async def _complete(self, system: str, user_msg: str) -> str:
        response = await self.client.chat.completions.create(
            model    = self.model,
            messages = [
                {"role": "system", "content": system},
                {"role": "user",   "content": user_msg},
            ],
        )
        return response.choices[0].message.content


# ── Factory ────────────────────────────────────────────────────────────────────

def get_llm(provider: str = "gemini", model: str | None = None) -> BaseLLM:
    """
    Instantiate the right LLM from a string — used in main.py and routes.
    Provider is read from LLM_PROVIDER env var if not passed directly.

    Examples:
        get_llm("claude")
        get_llm("gpt",    model="gpt-4-turbo")
        get_llm("gemini", model="gemini-1.5-flash")
        get_llm("ollama", model="mistral")
    """
    provider = provider or os.getenv("LLM_PROVIDER", "gemini")

    providers = {
        "claude": ClaudeLLM,
        "gpt":    GPT,
        "gemini": GeminiLLM,
        "ollama": OllamaLLM,
    }

    if provider not in providers:
        raise ValueError(f"Unknown provider '{provider}'. Choose from: {list(providers)}")

    cls = providers[provider]
    return cls(model) if model else cls()