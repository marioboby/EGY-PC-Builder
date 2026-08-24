from __future__ import annotations
import os
import asyncio
import logging

from google import genai
from google.genai import types, errors as genai_errors

from .base import BaseLLM

logger = logging.getLogger("uvicorn")


# ── Claude (Anthropic) ─────────────────────────────────────────────────────────

class ClaudeLLM(BaseLLM):
    MODEL_NAME = "claude-sonnet-4-5"

    def __init__(self, model: str = MODEL_NAME):
        import anthropic
        self.model  = model
        self.client = anthropic.AsyncAnthropic()  # reads ANTHROPIC_API_KEY

    async def _complete(self, system: str, user_msg: str) -> str:
        response = await self.client.messages.create(
            model      = self.model,
            max_tokens = 4096,
            system     = system,
            messages   = [{"role": "user", "content": user_msg}],
        )
        return response.content[0].text


# ── GPT (OpenAI) ───────────────────────────────────────────────────────────────

class GPT(BaseLLM):
    MODEL_NAME = "gpt-4o"

    def __init__(self, model: str = MODEL_NAME):
        from openai import AsyncOpenAI
        self.model  = model
        self.client = AsyncOpenAI(api_key=os.getenv("GPT_API_KEY"))

    async def _complete(self, system: str, user_msg: str) -> str:
        response = await self.client.chat.completions.create(
            model      = self.model,
            max_tokens = 4096,
            messages   = [
                {"role": "system", "content": system},
                {"role": "user",   "content": user_msg},
            ],
        )
        return response.choices[0].message.content


# ── Gemini (Google) ────────────────────────────────────────────────────────────

class GeminiLLM(BaseLLM):
    MODEL_NAME = "gemini-3.5-flash"

    # Retries only apply to transient server-side failures (500/503/etc, "high
    # demand" overload). Client errors (bad key, invalid request) fail fast —
    # retrying those just wastes the fallback-chain timeout budget.
    MAX_RETRIES = 3
    INITIAL_BACKOFF_SECONDS = 1.0  # doubles each attempt: 1s, 2s, 4s

    def __init__(self, model: str = MODEL_NAME):
        self.model_name = model
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    def __del__(self):
        self.client.close()

    async def _complete(self, system: str, user_msg: str) -> str:
        chat = self.client.aio.chats.create(
            model=self.model_name,
            config=types.GenerateContentConfig(
                system_instruction=system
            ),
        )

        delay = self.INITIAL_BACKOFF_SECONDS
        last_err: genai_errors.ServerError | None = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = await chat.send_message(user_msg)
                return response.text
            except genai_errors.ServerError as e:
                # 5xx from Gemini (503 UNAVAILABLE / "high demand" is the common
                # one, but 500 INTERNAL happens too) — worth a quick retry
                # before giving up on this provider entirely.
                last_err = e
                if attempt == self.MAX_RETRIES:
                    break
                logger.warning(
                    f"[Gemini] {e.code} {e.status} on attempt {attempt}/{self.MAX_RETRIES} "
                    f"— retrying in {delay:.0f}s"
                )
                await asyncio.sleep(delay)
                delay *= 2
            # ClientError (4xx — bad key, invalid request, etc.) and anything
            # else is not retried; it propagates immediately.

        logger.warning(f"[Gemini] giving up after {self.MAX_RETRIES} attempts: {last_err}")
        raise last_err


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


def get_fallback_chain(order: str | None = None) -> list[BaseLLM]:
    """
    Build the ordered provider list used by generate_build_with_fallback(),
    driven by an env var instead of a hardcoded list in main.py — this is
    what actually makes the fallback chain model-agnostic/configurable
    without a code change, same as get_llm() does for the single-provider path.

    Reads LLM_FALLBACK_ORDER as a comma-separated list, e.g.:
        LLM_FALLBACK_ORDER=gemini,gpt,claude,ollama

    Falls back to "gemini,gpt" (the previous hardcoded default) if unset.
    A provider that fails to instantiate (e.g. missing API key) is skipped
    with a warning rather than crashing the whole chain — better to build
    with N-1 providers than fail startup entirely.
    """
    order = order or os.getenv("LLM_FALLBACK_ORDER", "gemini,gpt")
    names = [name.strip() for name in order.split(",") if name.strip()]

    chain: list[BaseLLM] = []
    for name in names:
        try:
            chain.append(get_llm(name))
        except Exception as e:
            logger.warning(f"[get_fallback_chain] Skipping '{name}': {e}")

    if not chain:
        raise RuntimeError(
            f"No LLM providers could be instantiated from LLM_FALLBACK_ORDER={order!r}. "
            "Check your API keys / .env."
        )

    return chain